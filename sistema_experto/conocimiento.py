"""
Carga y validación de la base de conocimiento desde JSON.

El conocimiento vive fuera del código (conocimiento/*.json) para que
alguien que sabe del dominio pueda editarlo sin tocar Python. Por eso
el validador reporta TODOS los problemas juntos con mensajes claros.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .modelo import BaseDeConocimiento, Regla

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "conocimiento" / "diagnostico_pc.json"


class ErrorDeConocimiento(ValueError):
    def __init__(self, errores: list[str]):
        self.errores = errores
        detalle = "\n".join(f"  - {e}" for e in errores)
        super().__init__(f"La base de conocimiento tiene {len(errores)} error(es):\n{detalle}")


def cargar(ruta: str | Path = RUTA_POR_DEFECTO) -> BaseDeConocimiento:
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f, object_pairs_hook=_sin_claves_duplicadas)
    return desde_dict(datos)


def desde_dict(datos: dict[str, Any]) -> BaseDeConocimiento:
    errores: list[str] = []

    hechos = datos.get("hechos")
    if not isinstance(hechos, dict) or not hechos:
        raise ErrorDeConocimiento(["'hechos' debe ser un objeto no vacío"])
    reglas_crudas = datos.get("reglas")
    if not isinstance(reglas_crudas, list) or not reglas_crudas:
        raise ErrorDeConocimiento(["'reglas' debe ser una lista no vacía"])

    preguntas: dict[str, str] = {}
    for hecho, info in hechos.items():
        pregunta = info.get("pregunta") if isinstance(info, dict) else None
        if not isinstance(pregunta, str) or not pregunta.strip():
            errores.append(f"El hecho '{hecho}' no tiene una 'pregunta' válida")
        else:
            preguntas[hecho] = pregunta

    reglas = []
    for i, cruda in enumerate(reglas_crudas):
        regla = _construir_regla(cruda, i, errores)
        if regla is not None:
            reglas.append(regla)

    base = BaseDeConocimiento(
        nombre=datos.get("nombre", "Sistema experto"),
        preguntas=preguntas,
        reglas=tuple(reglas),
    )
    errores.extend(validar(base))
    if errores:
        raise ErrorDeConocimiento(errores)
    return base


def validar(base: BaseDeConocimiento) -> list[str]:
    """Chequeos de consistencia entre reglas. Devuelve la lista de errores."""
    errores: list[str] = []
    entradas = set(base.preguntas)
    derivados = base.hechos_derivados

    vistos: set[str] = set()
    for r in base.reglas:
        if r.id in vistos:
            errores.append(f"ID de regla duplicado: {r.id}")
        vistos.add(r.id)

    for r in base.reglas:
        if r.conclusion in entradas:
            errores.append(
                f"{r.id}: concluye '{r.conclusion}', que es un hecho de entrada "
                "(las reglas solo pueden concluir hechos derivados)"
            )
        for hecho, valor in r.condiciones.items():
            if hecho not in entradas and hecho not in derivados:
                errores.append(
                    f"{r.id}: la condición '{hecho}' no tiene pregunta "
                    "ni hay regla que la concluya"
                )
            elif hecho in derivados and valor is False:
                errores.append(
                    f"{r.id}: niega el hecho derivado '{hecho}'; solo se pueden "
                    "negar hechos de entrada (un hecho derivado nunca se afirma como falso)"
                )

    # Pregunta de reflexión 11: condiciones idénticas generan ambigüedad.
    por_condiciones: dict[frozenset, str] = {}
    for r in base.reglas:
        clave = frozenset(r.condiciones.items())
        if clave in por_condiciones:
            errores.append(
                f"{r.id} y {por_condiciones[clave]} tienen exactamente las mismas condiciones"
            )
        else:
            por_condiciones[clave] = r.id

    usados = {h for r in base.reglas for h in r.condiciones}
    for hecho in sorted(entradas - usados):
        errores.append(f"El hecho '{hecho}' tiene pregunta pero ninguna regla lo usa")

    ciclo = _buscar_ciclo(base)
    if ciclo:
        errores.append("Dependencia circular entre hechos: " + " → ".join(ciclo))

    return errores


# ── Auxiliares ────────────────────────────────────────────────

def _construir_regla(cruda: Any, indice: int, errores: list[str]) -> Regla | None:
    if not isinstance(cruda, dict):
        errores.append(f"La regla #{indice + 1} no es un objeto")
        return None
    id_regla = cruda.get("id") or f"#{indice + 1}"
    antes = len(errores)

    for campo in ("id", "descripcion", "entonces"):
        if not isinstance(cruda.get(campo), str) or not cruda[campo].strip():
            errores.append(f"Regla {id_regla}: falta el campo '{campo}'")

    condiciones = cruda.get("si")
    if not isinstance(condiciones, dict) or not condiciones:
        errores.append(f"Regla {id_regla}: 'si' debe ser un objeto no vacío {{hecho: true/false}}")
    elif not all(isinstance(v, bool) for v in condiciones.values()):
        errores.append(f"Regla {id_regla}: los valores de 'si' deben ser true o false")

    confianza = cruda.get("confianza")
    if isinstance(confianza, bool) or not isinstance(confianza, (int, float)) or not 0 < confianza <= 1:
        errores.append(f"Regla {id_regla}: 'confianza' debe ser un número en (0, 1]")

    recomendacion = cruda.get("recomendacion")
    if recomendacion is not None and not isinstance(recomendacion, str):
        errores.append(f"Regla {id_regla}: 'recomendacion' debe ser texto")

    if len(errores) > antes:
        return None
    return Regla(
        id=cruda["id"],
        descripcion=cruda["descripcion"],
        condiciones=dict(condiciones),
        conclusion=cruda["entonces"],
        confianza=float(confianza),
        recomendacion=recomendacion,
    )


def _buscar_ciclo(base: BaseDeConocimiento) -> list[str] | None:
    """DFS sobre el grafo hecho-condición → hecho-conclusión."""
    grafo: dict[str, set[str]] = {}
    for r in base.reglas:
        grafo.setdefault(r.conclusion, set()).update(r.condiciones)

    visitando: list[str] = []
    terminados: set[str] = set()

    def dfs(hecho: str) -> list[str] | None:
        if hecho in visitando:
            return visitando[visitando.index(hecho):] + [hecho]
        if hecho in terminados:
            return None
        visitando.append(hecho)
        for dependencia in grafo.get(hecho, ()):
            ciclo = dfs(dependencia)
            if ciclo:
                return ciclo
        visitando.pop()
        terminados.add(hecho)
        return None

    for hecho in grafo:
        ciclo = dfs(hecho)
        if ciclo:
            return ciclo
    return None


def _sin_claves_duplicadas(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    resultado: dict[str, Any] = {}
    for clave, valor in pares:
        if clave in resultado:
            raise ErrorDeConocimiento([f"Clave duplicada en el JSON: '{clave}'"])
        resultado[clave] = valor
    return resultado
