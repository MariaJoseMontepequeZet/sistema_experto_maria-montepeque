"""
Parte comercial de la API: identificar al cliente por su clave, aplicar su plan (límite por minuto y cuota
mensual), contar sus consultas y administrar clientes.

Dos modos, según la configuración:
    abierto     sin SISTEMA_EXPERTO_ADMIN_KEY: la API funciona como antes (abierta, o con las claves de
                SISTEMA_EXPERTO_API_KEYS) y no cuenta consultas. Es el modo de desarrollo.
    comercial   con SISTEMA_EXPERTO_ADMIN_KEY: cada llamada exige la clave de un cliente dado de alta,
                aplica su plan y cuenta sus consultas. Las de SISTEMA_EXPERTO_API_KEYS dejan de usarse.
"""

from __future__ import annotations

import os
import re
import secrets
import time
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from .clientes import (
    Almacen,
    Cliente,
    CuotaAgotada,
    LimitadorPorMinuto,
    ahora,
    huella_consulta,
    periodo_de,
)
from .modelo import Valor
from .planes import POR_USO, Plan, cargar_planes

PLANES: dict[str, Plan] = cargar_planes()
_limitador = LimitadorPorMinuto()
reloj = time.monotonic     # las pruebas lo reemplazan

# cada esquema lleva su propio nombre: si no, Swagger los fusiona y solo deja escribir una de las dos claves
_cabecera_clave = APIKeyHeader(name="X-API-Key", scheme_name="Clave de API", auto_error=False)
_cabecera_admin = APIKeyHeader(name="X-Admin-Key", scheme_name="Clave de administración", auto_error=False)


@lru_cache(maxsize=8)
def _almacen_en(ruta: str) -> Almacen:
    return Almacen(ruta or None)


def almacen() -> Almacen:
    """El almacén de la ruta que indique SISTEMA_EXPERTO_BD en este momento."""
    return _almacen_en(os.environ.get("SISTEMA_EXPERTO_BD", ""))


def modo_comercial() -> bool:
    return bool(os.environ.get("SISTEMA_EXPERTO_ADMIN_KEY"))


# ── Identificación y límites ──────────────────────────────────

def exigir_clave(clave: Annotated[str | None, Security(_cabecera_clave)] = None) -> Cliente | None:
    """
    Modo abierto: exige una de SISTEMA_EXPERTO_API_KEYS si hay, y devuelve None.
    Modo comercial: exige la clave de un cliente activo, aplica su límite por minuto y lo devuelve.
    """
    if not modo_comercial():
        validas = [k.strip() for k in os.environ.get("SISTEMA_EXPERTO_API_KEYS", "").split(",") if k.strip()]
        if validas and not (clave and any(secrets.compare_digest(clave, v) for v in validas)):
            raise HTTPException(401, "Clave de API ausente o inválida (cabecera X-API-Key).")
        return None

    cliente = almacen().buscar_por_clave(clave) if clave else None
    if cliente is None:
        raise HTTPException(401, "Clave de API ausente o inválida (cabecera X-API-Key).")
    if not cliente.activo:
        raise HTTPException(403, "La cuenta está suspendida. Contacta a soporte.")
    plan = PLANES.get(cliente.plan)
    if plan is None:
        raise HTTPException(403, f"El plan '{cliente.plan}' de tu cuenta ya no existe. Contacta a soporte.")
    espera = _limitador.permitir(cliente.id, plan.limite_por_minuto, reloj())
    if espera is not None:
        raise HTTPException(429, f"Demasiadas llamadas: tu plan admite {plan.limite_por_minuto} por minuto.",
                            headers={"Retry-After": str(espera)})
    return cliente


def cobrar(cliente: Cliente | None, respuestas: dict[str, Valor], respuesta: Response) -> None:
    """
    Cuenta un diagnóstico entregado. Sin cliente (modo abierto) no hace nada. Si el plan mensual ya no
    tiene consultas, responde 402 sin entregar el diagnóstico.
    """
    if cliente is None:
        return
    plan = PLANES[cliente.plan]
    periodo = periodo_de(ahora())
    try:
        _, usadas = almacen().registrar_consulta(cliente.id, huella_consulta(respuestas), periodo,
                                                 plan.consultas_incluidas)
    except CuotaAgotada as agotada:
        raise HTTPException(402, f"{agotada} Se renueva el mes siguiente; para seguir antes, "
                                 "cambia a un plan con más consultas.") from agotada
    respuesta.headers["X-Consultas-Usadas"] = str(usadas)
    restantes = plan.restantes(usadas)
    if restantes is not None:
        respuesta.headers["X-Consultas-Restantes"] = str(restantes)


# ── Rutas del cliente ─────────────────────────────────────────

router = APIRouter()


@router.get("/v1/uso", tags=["Cuenta"])
def uso(cliente: Annotated[Cliente | None, Depends(exigir_clave)]) -> dict:
    """Tu plan, las consultas que llevas este mes y lo que costaría facturarlas."""
    if cliente is None:
        raise HTTPException(404, "El modo comercial no está activo: no hay cuenta que consultar.")
    periodo = periodo_de(ahora())
    return _resumen(cliente, periodo, almacen().consumo(cliente.id, periodo))


def _resumen(cliente: Cliente, periodo: str, consultas: int) -> dict:
    plan = PLANES.get(cliente.plan)
    return {
        "cliente": cliente.nombre,
        "plan": cliente.plan,
        "nombre_plan": plan.nombre if plan else None,
        "periodo": periodo,
        "consultas": consultas,
        "incluidas": plan.consultas_incluidas if plan else None,
        "restantes": plan.restantes(consultas) if plan else None,
        "limite_por_minuto": plan.limite_por_minuto if plan else None,
        "importe_usd": plan.importe(consultas) if plan else None,
    }


# ── Administración ────────────────────────────────────────────

def exigir_admin(clave: Annotated[str | None, Security(_cabecera_admin)] = None) -> None:
    esperada = os.environ.get("SISTEMA_EXPERTO_ADMIN_KEY")
    if not esperada:
        raise HTTPException(404, "Not Found")      # sin clave de administración, estas rutas no existen
    if not (clave and secrets.compare_digest(clave, esperada)):
        raise HTTPException(403, "Clave de administración ausente o inválida (cabecera X-Admin-Key).")


admin = APIRouter(prefix="/admin", tags=["Administración"], dependencies=[Depends(exigir_admin)])


class NuevoCliente(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    plan: str


class CambioCliente(BaseModel):
    plan: str | None = None
    activo: bool | None = None


def _plan_valido(plan: str) -> None:
    if plan not in PLANES:
        raise HTTPException(422, f"El plan '{plan}' no existe (planes: {', '.join(PLANES)}).")


def _existente(cliente_id: int) -> Cliente:
    cliente = almacen().cliente(cliente_id)
    if cliente is None:
        raise HTTPException(404, f"No existe el cliente {cliente_id}.")
    return cliente


@admin.post("/clientes", status_code=201)
def crear_cliente(datos: NuevoCliente) -> dict:
    """Da de alta a un cliente. La clave completa **solo se muestra esta vez**: guárdala."""
    _plan_valido(datos.plan)
    cliente, clave = almacen().crear_cliente(datos.nombre, datos.plan)
    return {"id": cliente.id, "nombre": cliente.nombre, "plan": cliente.plan, "clave": clave}


@admin.get("/clientes")
def listar_clientes() -> list[dict]:
    periodo = periodo_de(ahora())
    consumo = almacen().consumo_por_cliente(periodo)
    return [{**_resumen(c, periodo, consumo.get(c.id, 0)), "id": c.id, "activo": c.activo,
             "claves": almacen().claves(c.id)} for c in almacen().clientes()]


@admin.put("/clientes/{cliente_id}")
def cambiar_cliente(cliente_id: int, cambio: CambioCliente) -> dict:
    """Cambia el plan o suspende/reactiva la cuenta (suspendida, sus claves dejan de funcionar)."""
    _existente(cliente_id)
    if cambio.plan is not None:
        _plan_valido(cambio.plan)
    almacen().cambiar(cliente_id, cambio.plan, cambio.activo)
    cliente = _existente(cliente_id)
    return {"id": cliente.id, "nombre": cliente.nombre, "plan": cliente.plan, "activo": cliente.activo}


@admin.post("/clientes/{cliente_id}/claves", status_code=201)
def nueva_clave(cliente_id: int) -> dict:
    """Emite otra clave para el cliente (al rotarla). La anterior sigue activa hasta revocarla."""
    _existente(cliente_id)
    return {"cliente": cliente_id, "clave": almacen().nueva_clave(cliente_id)}


@admin.delete("/claves/{prefijo}")
def revocar_clave(prefijo: str) -> dict:
    """Desactiva una clave (se identifica por sus primeros 11 caracteres, que se ven en el listado)."""
    if not almacen().revocar_clave(prefijo):
        raise HTTPException(404, f"No hay una clave activa con el prefijo '{prefijo}'.")
    return {"revocada": prefijo}


@admin.get("/facturacion")
def facturacion(periodo: str | None = None) -> dict:
    """Lo que hay que facturar a cada cliente en un mes (`AAAA-MM`; por defecto, el actual)."""
    periodo = periodo or periodo_de(ahora())
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", periodo):
        raise HTTPException(422, "El periodo debe tener la forma AAAA-MM, por ejemplo 2026-10.")
    consumo = almacen().consumo_por_cliente(periodo)
    filas = []
    for c in almacen().clientes():
        plan = PLANES.get(c.plan)
        consultas = consumo.get(c.id, 0)
        # un plan mensual se factura aunque no haya consultado (si la cuenta sigue activa);
        # uno por uso, solo si hizo consultas
        if plan and (consultas or (plan.tipo != POR_USO and c.activo)):
            filas.append({"id": c.id, "cliente": c.nombre, "plan": c.plan, "consultas": consultas,
                          "importe_usd": plan.importe(consultas)})
    total = round(sum(f["importe_usd"] for f in filas), 2)
    return {"periodo": periodo, "clientes": filas, "total_usd": total}


router.include_router(admin)
