"""
Validación del sistema experto contra casos de referencia.

Cada caso describe lo que observaría el usuario (y el resultado de las pruebas que haría)
y el diagnóstico correcto. Cada caso se resuelve con la consulta dinámica completa, como
lo haría un usuario real: lo que el caso no indica se responde "no sé".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .conocimiento import ErrorDeConocimiento
from .modelo import BaseDeConocimiento, Valor, porcentaje
from .motor import encadenar_hacia_adelante, siguiente_pregunta

RUTA_CASOS = Path(__file__).resolve().parent.parent / "casos" / "casos_referencia.json"

# Precisión mínima exigida en el CI sobre los casos que el conocimiento cubre.
PRECISION_MINIMA = 0.9

# Rangos de certeza para medir la calibración: ¿cuando dice 90 %, acierta 9 de cada 10?
RANGOS_CALIBRACION = ((0.2, 0.5), (0.5, 0.8), (0.8, 0.9), (0.9, 1.0))


@dataclass(frozen=True)
class Caso:
    id: str
    descripcion: str
    respuestas: dict[str, Valor]      # la "verdad" del caso: lo que respondería el usuario
    esperado: str | None              # diagnóstico correcto; None = equipo sin falla
    fuente: str = ""


@dataclass(frozen=True)
class ResultadoCaso:
    caso: Caso
    ranking: tuple[str, ...]          # diagnósticos obtenidos, de mayor a menor certeza
    certeza: float | None             # certeza del diagnóstico principal
    preguntas: int                    # preguntas que hizo la consulta dinámica
    cubierto: bool                    # el conocimiento incluye el diagnóstico esperado

    @property
    def obtenido(self) -> str | None:
        return self.ranking[0] if self.ranking else None

    @property
    def acierto(self) -> bool:
        return self.obtenido == self.caso.esperado

    @property
    def en_top3(self) -> bool:
        return self.acierto if self.caso.esperado is None else self.caso.esperado in self.ranking[:3]


@dataclass(frozen=True)
class Evaluacion:
    resultados: tuple[ResultadoCaso, ...]

    @property
    def cubiertos(self) -> list[ResultadoCaso]:
        return [r for r in self.resultados if r.cubierto]

    @property
    def fuera_de_cobertura(self) -> list[ResultadoCaso]:
        return [r for r in self.resultados if not r.cubierto]

    @property
    def fallos(self) -> list[ResultadoCaso]:
        return [r for r in self.cubiertos if not r.acierto]

    @property
    def precision(self) -> float:
        cubiertos = self.cubiertos
        return sum(r.acierto for r in cubiertos) / len(cubiertos) if cubiertos else 0.0

    @property
    def precision_top3(self) -> float:
        cubiertos = self.cubiertos
        return sum(r.en_top3 for r in cubiertos) / len(cubiertos) if cubiertos else 0.0

    @property
    def falsos_positivos(self) -> list[ResultadoCaso]:
        """Equipos sin falla a los que el sistema les atribuyó una."""
        return [r for r in self.resultados if r.caso.esperado is None and r.obtenido is not None]

    @property
    def preguntas_promedio(self) -> float:
        return sum(r.preguntas for r in self.resultados) / len(self.resultados) if self.resultados else 0.0

    def calibracion(self) -> list[tuple[str, int, float | None]]:
        """(rango, casos con diagnóstico en ese rango de certeza, proporción de aciertos)."""
        filas = []
        for desde, hasta in RANGOS_CALIBRACION:
            casos = [r for r in self.cubiertos
                     if r.certeza is not None and desde <= r.certeza < hasta + (hasta == 1.0)]
            aciertos = sum(r.acierto for r in casos) / len(casos) if casos else None
            filas.append((f"{desde * 100:.0f}–{hasta * 100:.0f} %", len(casos), aciertos))
        return filas


def cargar_casos(base: BaseDeConocimiento, ruta: str | Path = RUTA_CASOS) -> list[Caso]:
    """Lee los casos, aplica sus plantillas y comprueba que cada respuesta sea válida."""
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    plantillas: dict[str, dict[str, Any]] = datos.get("plantillas", {})
    errores: list[str] = []
    casos: list[Caso] = []
    vistos: set[str] = set()

    for crudo in datos.get("casos", []):
        id_caso = crudo.get("id", "?")
        if id_caso in vistos:
            errores.append(f"Caso {id_caso}: ID duplicado")
        vistos.add(id_caso)

        nombre_plantilla = crudo.get("plantilla")
        if nombre_plantilla is not None and nombre_plantilla not in plantillas:
            errores.append(f"Caso {id_caso}: la plantilla '{nombre_plantilla}' no existe")
            continue
        respuestas = {**plantillas.get(nombre_plantilla, {}), **crudo.get("respuestas", {})}

        for hecho, valor in respuestas.items():
            if hecho not in base.hechos:
                errores.append(f"Caso {id_caso}: '{hecho}' no es una pregunta de la base de conocimiento")
            elif not base.hechos[hecho].admite(valor):
                errores.append(f"Caso {id_caso}: {valor!r} no es una respuesta válida para '{hecho}'")

        if "esperado" not in crudo:
            errores.append(f"Caso {id_caso}: falta 'esperado' (un diagnóstico, o null si no hay falla)")
        casos.append(Caso(id=id_caso, descripcion=crudo.get("descripcion", ""), respuestas=respuestas,
                          esperado=crudo.get("esperado"), fuente=crudo.get("fuente", "")))

    if errores:
        raise ErrorDeConocimiento(errores)
    return casos


def simular_consulta(base: BaseDeConocimiento, verdad: dict[str, Valor]) -> dict[str, Valor]:
    """Consulta dinámica en la que el usuario responde según `verdad` ("no sé" si no está)."""
    respuestas: dict[str, Valor] = {}
    while (pregunta := siguiente_pregunta(base, respuestas)) is not None:
        respuestas[pregunta.hecho] = verdad.get(pregunta.hecho)
    return respuestas


def evaluar(base: BaseDeConocimiento, casos: list[Caso]) -> Evaluacion:
    resultados = []
    for caso in casos:
        respuestas = simular_consulta(base, caso.respuestas)
        diagnosticos = encadenar_hacia_adelante(base, respuestas).diagnosticos
        cubierto = caso.esperado is None or caso.esperado in base.hechos_diagnostico
        resultados.append(ResultadoCaso(
            caso=caso,
            ranking=tuple(dg.hecho for dg in diagnosticos),
            certeza=diagnosticos[0].certeza if diagnosticos else None,
            preguntas=len(respuestas),
            cubierto=cubierto,
        ))
    return Evaluacion(tuple(resultados))


def informe(evaluacion: Evaluacion) -> str:
    """Resumen legible de la evaluación."""
    cubiertos = evaluacion.cubiertos
    lineas = [
        f"Casos de referencia: {len(evaluacion.resultados)} "
        f"({len(cubiertos)} cubiertos por el conocimiento, "
        f"{len(evaluacion.fuera_de_cobertura)} fuera de cobertura)",
        "",
        f"  Precisión (diagnóstico principal correcto): {evaluacion.precision * 100:.1f} % "
        f"({sum(r.acierto for r in cubiertos)} de {len(cubiertos)})",
        f"  Diagnóstico correcto entre los 3 primeros:  {evaluacion.precision_top3 * 100:.1f} %",
        f"  Falsos positivos (falla inventada):         {len(evaluacion.falsos_positivos)}",
        f"  Preguntas promedio por consulta:            {evaluacion.preguntas_promedio:.1f}",
        "",
        "  Calibración (certeza del sistema vs. aciertos reales):",
    ]
    for rango, n, aciertos in evaluacion.calibracion():
        detalle = "—" if aciertos is None else f"acierta {aciertos * 100:.0f} %"
        lineas.append(f"    certeza {rango:<10} {n:>3} casos   {detalle}")

    if evaluacion.fallos:
        lineas += ["", "  Fallos:"]
        for r in evaluacion.fallos:
            obtenido = r.obtenido or "sin diagnóstico"
            certeza = f" ({porcentaje(r.certeza)})" if r.certeza is not None else ""
            esperado = r.caso.esperado or "sin falla"
            lineas.append(f"    ✗ {r.caso.id} {r.caso.descripcion}: esperaba {esperado}, "
                          f"obtuvo {obtenido}{certeza}")

    if evaluacion.fuera_de_cobertura:
        lineas += ["", "  Fuera de cobertura (fallas que el conocimiento todavía no incluye):"]
        for r in evaluacion.fuera_de_cobertura:
            lineas.append(f"    · {r.caso.id} {r.caso.descripcion} → {r.caso.esperado}")
    return "\n".join(lineas)
