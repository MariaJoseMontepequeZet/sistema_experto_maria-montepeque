"""
Planes comerciales: cuánto cuesta, cuántas consultas incluye y cuántas llamadas por minuto admite.

Se leen de `configuracion/planes.json` (o de la ruta en SISTEMA_EXPERTO_PLANES), así se cambian precios y
cuotas sin tocar el código. Dos tipos de plan:

    por_uso   se paga `precio_usd` por cada consulta (diagnóstico entregado); sin tope mensual
    mensual   se paga `precio_usd` fijos al mes e incluye `consultas_incluidas`; agotadas, se espera al mes
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "configuracion" / "planes.json"
POR_USO = "por_uso"
MENSUAL = "mensual"
CAMPOS = {"nombre", "tipo", "precio_usd", "consultas_incluidas", "limite_por_minuto"}


class ErrorDePlanes(ValueError):
    """El archivo de planes tiene errores (se reportan todos juntos)."""


@dataclass(frozen=True)
class Plan:
    id: str
    nombre: str
    tipo: str
    precio_usd: float
    consultas_incluidas: int | None   # solo en planes mensuales
    limite_por_minuto: int

    def importe(self, consultas: int) -> float:
        """Lo que se factura en un mes en que el cliente hizo `consultas` consultas."""
        if self.tipo == POR_USO:
            return round(self.precio_usd * consultas, 2)
        return round(self.precio_usd, 2)

    def restantes(self, consultas: int) -> int | None:
        """Consultas que quedan en el mes; None si el plan no tiene tope."""
        if self.consultas_incluidas is None:
            return None
        return max(0, self.consultas_incluidas - consultas)


def cargar_planes(ruta: str | Path | None = None) -> dict[str, Plan]:
    ruta = Path(ruta or os.environ.get("SISTEMA_EXPERTO_PLANES") or RUTA_POR_DEFECTO)
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    errores: list[str] = []
    planes: dict[str, Plan] = {}
    if not isinstance(datos, dict) or not datos:
        raise ErrorDePlanes("El archivo de planes debe ser un objeto con al menos un plan.")
    for id_plan, d in datos.items():
        if not isinstance(d, dict):
            errores.append(f"{id_plan}: debe ser un objeto.")
            continue
        sobran = sorted(set(d) - CAMPOS)
        if sobran:
            errores.append(f"{id_plan}: campos desconocidos {sobran} (permitidos: {sorted(CAMPOS)}).")
        tipo = d.get("tipo")
        if tipo not in (POR_USO, MENSUAL):
            errores.append(f"{id_plan}: 'tipo' debe ser '{POR_USO}' o '{MENSUAL}'.")
        for campo in ("precio_usd", "limite_por_minuto"):
            if not _numero(d.get(campo)) or d[campo] < 0:
                errores.append(f"{id_plan}: '{campo}' debe ser un número mayor o igual a cero.")
        incluidas = d.get("consultas_incluidas")
        if tipo == MENSUAL and not (isinstance(incluidas, int) and not isinstance(incluidas, bool)
                                    and incluidas > 0):
            errores.append(f"{id_plan}: un plan mensual necesita 'consultas_incluidas' (entero > 0).")
        if tipo == POR_USO and incluidas is not None:
            errores.append(f"{id_plan}: un plan por uso no tiene 'consultas_incluidas'.")
        if not errores:
            planes[id_plan] = Plan(id_plan, str(d.get("nombre", id_plan)), tipo, d["precio_usd"],
                                   incluidas, int(d["limite_por_minuto"]))
    if errores:
        raise ErrorDePlanes("\n".join(errores))
    return planes


def _numero(valor: object) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)
