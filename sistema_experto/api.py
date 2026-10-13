"""
API REST del sistema experto (FastAPI).

    python -m uvicorn sistema_experto.api:app

Igual que cli.py y app.py, solo presenta: toda la lógica vive en el motor. La API no guarda estado:
en cada llamada el cliente envía todas las respuestas que lleva y recibe la siguiente pregunta o el
diagnóstico. Así se puede escalar sin sesiones y cada cliente (web, móvil, un script recolector)
decide cómo guardar la consulta.

Configuración por variables de entorno (la parte comercial está en comercial.py y docs/comercial.md):
    SISTEMA_EXPERTO_ADMIN_KEY     activa el modo comercial (clientes con clave, plan y cuota)
    SISTEMA_EXPERTO_BD            ruta de la base de datos de clientes (SQLite)
    SISTEMA_EXPERTO_PLANES        ruta de otro archivo de planes y precios
    SISTEMA_EXPERTO_API_KEYS      modo abierto: claves válidas separadas por comas; sin ellas, API abierta
    SISTEMA_EXPERTO_CONOCIMIENTO  ruta de otra base de conocimiento JSON
    SISTEMA_EXPERTO_CORS          orígenes permitidos separados por comas (frontend en otro dominio)
"""

from __future__ import annotations

import base64
import binascii
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .clientes import Cliente
from .comercial import cobrar, exigir_clave
from .comercial import router as rutas_comerciales
from .conocimiento import RUTA_POR_DEFECTO, cargar
from .informe import DatosServicio, Marca, generar_pdf
from .modelo import NUMERO, OPCION, Hecho, Valor, porcentaje
from .motor import (
    Diagnostico,
    Inferencia,
    Pregunta,
    encadenar_hacia_adelante,
    hipotesis_abiertas,
    pregunta_sobre,
    siguiente_pregunta,
)
from .validacion import cargar_casos, evaluar

VERSION = "1.9.0"
BASE = cargar(Path(os.environ.get("SISTEMA_EXPERTO_CONOCIMIENTO") or RUTA_POR_DEFECTO))
DIAGNOSTICOS_POSIBLES = len(BASE.hechos_diagnostico)
RUTA_WEB = Path(__file__).resolve().parent.parent / "web" / "public"

app = FastAPI(
    title="Sistema experto: diagnóstico de PC",
    version=VERSION,
    description="Consulta dinámica sin estado: envía las respuestas que llevas y recibe la siguiente "
                "pregunta o el diagnóstico con su razonamiento.",
)

_origenes = [o.strip() for o in os.environ.get("SISTEMA_EXPERTO_CORS", "").split(",") if o.strip()]
if _origenes:
    app.add_middleware(CORSMiddleware, allow_origins=_origenes,
                       allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["X-API-Key", "X-Admin-Key", "Content-Type"])
app.include_router(rutas_comerciales)


# ── Modelos de entrada ────────────────────────────────────────

class Consulta(BaseModel):
    respuestas: dict[str, bool | float | str | None] = Field(
        default_factory=dict,
        description="hecho -> respuesta: true/false, la clave de una opción, un número o null para 'no sé'.",
        examples=[{"enciende": False, "tipo_equipo": "escritorio"}],
    )
    completo: bool = Field(False, description="Hacer todas las preguntas en orden, sin consulta dinámica.")
    omitir_pruebas: bool = Field(False, description="Terminar sin las pruebas de verificación que faltan.")


class MarcaEntrada(BaseModel):
    """Identidad del taller en el encabezado del informe."""
    nombre: str = Field("Informe de diagnóstico", max_length=80)
    color: str = Field("#1f4e79", pattern=r"^#[0-9a-fA-F]{6}$", description="Color del encabezado, #rrggbb.")
    contacto: str = Field("", max_length=120, description="Teléfono, correo o dirección.")
    logo_base64: str | None = Field(None, max_length=700_000,
                                    description="Logo PNG o JPG en base64 (hasta ~500 KB).")


class ServicioEntrada(BaseModel):
    cliente: str = Field("", max_length=80)
    equipo: str = Field("", max_length=120, description="Por ejemplo: Laptop HP 15, serie XYZ.")
    tecnico: str = Field("", max_length=80)
    observaciones: str = Field("", max_length=500)


class ConsultaInforme(Consulta):
    marca: MarcaEntrada = Field(default_factory=MarcaEntrada)
    servicio: ServicioEntrada = Field(default_factory=ServicioEntrada)


def validar(consulta: Consulta) -> dict[str, Valor]:
    """Rechaza hechos desconocidos y respuestas que el hecho no admite."""
    errores = []
    for hecho, valor in consulta.respuestas.items():
        if hecho not in BASE.hechos:
            errores.append(f"'{hecho}' no es un hecho de la base de conocimiento.")
        elif not BASE.hechos[hecho].admite(valor):
            errores.append(f"{valor!r} no es una respuesta válida para '{hecho}' "
                           f"({_describir_entrada(BASE.hechos[hecho])}).")
    if errores:
        raise HTTPException(422, errores)
    return dict(consulta.respuestas)


def _describir_entrada(hecho: Hecho) -> str:
    if hecho.tipo == OPCION:
        return "una de: " + ", ".join(hecho.valores_opcion)
    if hecho.tipo == NUMERO:
        return f"un número entre {hecho.minimo} y {hecho.maximo}"
    return "true, false o null"


# ── Serialización ─────────────────────────────────────────────

def _entrada(hecho: Hecho) -> dict:
    return {
        "hecho": hecho.nombre,
        "texto": hecho.pregunta,
        "tipo": hecho.tipo,
        "opciones": [{"valor": v, "etiqueta": e} for v, e in hecho.opciones],
        "unidad": hecho.unidad or None,
        "minimo": hecho.minimo,
        "maximo": hecho.maximo,
        "ayuda": hecho.ayuda,
        "prueba": hecho.prueba,
    }


def _pregunta(pregunta: Pregunta) -> dict:
    return {
        **_entrada(pregunta.entrada),
        "hipotesis": [
            {"regla": r.id, "descripcion": r.descripcion, "es_diagnostico": r.es_diagnostico,
             "confianza": r.confianza, "en_contra": r.en_contra, "conclusion": r.conclusion}
            for r in pregunta.hipotesis
        ],
        "rivales": [{"hecho": dg.hecho, "descripcion": dg.descripcion, "certeza": dg.certeza}
                    for dg in pregunta.rivales],
    }


def _diagnostico(dg: Diagnostico, inferencia: Inferencia) -> dict:
    return {
        "hecho": dg.hecho,
        "descripcion": dg.descripcion,
        "certeza": dg.certeza,
        "certeza_texto": porcentaje(dg.certeza),
        "recomendaciones": dg.recomendaciones,
        "advertencias": dg.advertencias,
        "evidencias": [{"regla": d.regla.id, "descripcion": d.regla.descripcion, "certeza": d.certeza}
                       for d in dg.disparos],
        "razonamiento": [
            {"ciclo": d.ciclo, "regla": d.regla.id, "descripcion": d.regla.descripcion,
             "si": [f"{h} = {BASE.describir(h, c)}" for h, c in d.regla.condiciones.items()],
             "entonces": d.regla.conclusion, "certeza": d.certeza}
            for d in inferencia.justificacion(dg.hecho)
        ],
    }


# ── Rutas ─────────────────────────────────────────────────────

@app.get("/salud", tags=["Estado"])
def salud() -> dict:
    """Comprobación de que el servicio está arriba (para balanceadores y monitoreo)."""
    return {"estado": "ok", "version": VERSION, "base": BASE.nombre}


@app.get("/v1/conocimiento", tags=["Conocimiento"], dependencies=[Depends(exigir_clave)])
def conocimiento() -> dict:
    """Las preguntas que sabe hacer el sistema y cuántos diagnósticos cubre."""
    return {
        "nombre": BASE.nombre,
        "reglas": len(BASE.reglas),
        "diagnosticos": DIAGNOSTICOS_POSIBLES,
        "preguntas": [_entrada(h) for h in BASE.hechos.values()],
    }


@app.post("/v1/consulta/siguiente", tags=["Consulta"], dependencies=[Depends(exigir_clave)])
def siguiente(consulta: Consulta) -> dict:
    """
    Dadas las respuestas hasta ahora, devuelve la próxima pregunta, o `terminada: true`
    cuando no queda nada útil por preguntar (entonces se pide el resultado).
    """
    r = validar(consulta)
    pregunta = None
    if not consulta.omitir_pruebas:
        if consulta.completo:
            faltan = [h for h in BASE.preguntas if h not in r]
            pregunta = pregunta_sobre(BASE, r, faltan[0]) if faltan else None
        else:
            pregunta = siguiente_pregunta(BASE, r)
    return {
        "terminada": pregunta is None,
        "pregunta": _pregunta(pregunta) if pregunta else None,
        "progreso": {
            "respondidas": len(r),
            # fallas distintas, no reglas (cada falla tiene varias)
            "hipotesis_abiertas": len({a.regla.conclusion for a in hipotesis_abiertas(BASE, r)}),
            "diagnosticos_posibles": DIAGNOSTICOS_POSIBLES,
        },
    }


@app.post("/v1/consulta/resultado", tags=["Consulta"], dependencies=[Depends(exigir_clave)])
def resultado(consulta: Consulta, respuesta: Response,
              cliente: Annotated[Cliente | None, Depends(exigir_clave)]) -> dict:
    """
    El diagnóstico con las respuestas dadas: ordenado por certeza, con su evidencia y razonamiento.
    Es la llamada que cuenta como una consulta del plan (una vez por conjunto de respuestas al mes).
    """
    r = validar(consulta)
    cobrar(cliente, r, respuesta)
    inferencia = encadenar_hacia_adelante(BASE, r)
    return {
        "respondidas": len(r),
        "diagnosticos": [_diagnostico(dg, inferencia) for dg in inferencia.diagnosticos],
        "descartados": [
            {"hecho": dg.hecho, "descripcion": dg.descripcion,
             "motivos": [d.regla.descripcion for d in dg.en_contra]}
            for dg in inferencia.descartados
        ],
        "aviso": ("Este sistema orienta, no reemplaza a un técnico. "
                  "Apaga y desconecta el equipo antes de abrirlo."),
    }


@app.post("/v1/consulta/informe", tags=["Consulta"], dependencies=[Depends(exigir_clave)],
          response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def informe(consulta: ConsultaInforme, cliente: Annotated[Cliente | None, Depends(exigir_clave)]) -> Response:
    """
    El diagnóstico de `/resultado` como PDF con la marca del taller, listo para entregar al cliente.
    Si ya pediste el diagnóstico con las mismas respuestas este mes, no cuenta otra consulta.
    """
    r = validar(consulta)
    try:
        logo_texto = consulta.marca.logo_base64
        logo = base64.b64decode(logo_texto, validate=True) if logo_texto else None
        marca = Marca(consulta.marca.nombre, consulta.marca.color, consulta.marca.contacto, logo)
    except (binascii.Error, ValueError, OSError) as error:
        raise HTTPException(422, f"El logo no es una imagen PNG o JPG válida en base64 ({error}).") from error
    entrega = Response()
    cobrar(cliente, r, entrega)
    pdf = generar_pdf(BASE, r, encadenar_hacia_adelante(BASE, r), marca,
                      DatosServicio(**consulta.servicio.model_dump()))
    # solo las cabeceras de consumo: copiar todas arrastraría el content-length: 0 de la respuesta vacía
    consumo = {k: v for k, v in entrega.headers.items() if k.startswith("x-consultas")}
    return Response(pdf, media_type="application/pdf", headers={
        **consumo, "Content-Disposition": 'attachment; filename="informe-diagnostico.pdf"'})


@lru_cache(maxsize=1)
def _precision() -> dict:
    evaluacion = evaluar(BASE, cargar_casos(BASE))
    return {
        "precision": evaluacion.precision,
        "aciertos": sum(r.acierto for r in evaluacion.cubiertos),
        "casos_cubiertos": len(evaluacion.cubiertos),
        "fuera_de_cobertura": len(evaluacion.fuera_de_cobertura),
        "falsos_positivos": len(evaluacion.falsos_positivos),
        "preguntas_promedio": evaluacion.preguntas_promedio,
    }


@app.get("/v1/precision", tags=["Conocimiento"], dependencies=[Depends(exigir_clave)])
def precision() -> dict:
    """Precisión medida con los casos de referencia (se calcula una vez por arranque)."""
    return _precision()


# ── Interfaz web (web/, en TypeScript) ────────────────────────

if RUTA_WEB.is_dir():
    @app.get("/", include_in_schema=False)
    def inicio() -> RedirectResponse:
        return RedirectResponse("/app/")

    app.mount("/app", StaticFiles(directory=RUTA_WEB, html=True), name="web")
