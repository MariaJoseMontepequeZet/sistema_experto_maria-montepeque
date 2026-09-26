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

from .modelo import NUMERO, OPCION, SI_NO, TIPOS, BaseDeConocimiento, Condicion, Hecho, Regla, es_numero

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "conocimiento" / "diagnostico_pc.json"

CAMPOS_REGLA = {"id", "descripcion", "si", "entonces", "recomendacion", "advertencia", "confianza"}
CAMPOS_HECHO = {
    SI_NO: {"pregunta", "tipo", "ayuda"},
    OPCION: {"pregunta", "tipo", "ayuda", "opciones"},
    NUMERO: {"pregunta", "tipo", "ayuda", "unidad", "minimo", "maximo"},
}


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

    entradas: dict[str, Hecho] = {}
    for nombre, info in hechos.items():
        hecho = _construir_hecho(nombre, info, errores)
        if hecho is not None:
            entradas[nombre] = hecho

    reglas = []
    for i, cruda in enumerate(reglas_crudas):
        regla = _construir_regla(cruda, i, errores)
        if regla is not None:
            reglas.append(regla)

    base = BaseDeConocimiento(
        nombre=datos.get("nombre", "Sistema experto"),
        hechos=entradas,
        reglas=tuple(reglas),
    )
    errores.extend(validar(base))
    if errores:
        raise ErrorDeConocimiento(errores)
    return base


def validar(base: BaseDeConocimiento) -> list[str]:
    """Chequeos de consistencia entre reglas. Devuelve la lista de errores."""
    errores: list[str] = []
    entradas = set(base.hechos)
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
        for hecho, condicion in r.condiciones.items():
            if hecho in entradas:
                errores.extend(_validar_condicion(r.id, base.hechos[hecho], condicion))
            elif hecho not in derivados:
                errores.append(
                    f"{r.id}: la condición '{hecho}' no tiene pregunta "
                    "ni hay regla que la concluya"
                )
            elif condicion.esperado is False:
                errores.append(
                    f"{r.id}: niega el hecho derivado '{hecho}'; solo se pueden "
                    "negar hechos de entrada (un hecho derivado nunca se afirma como falso)"
                )
            elif condicion.esperado is not True:
                errores.append(f"{r.id}: '{hecho}' es un hecho derivado; la condición solo puede ser true")

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

    condiciones: dict[str, Condicion] = {}
    crudas = cruda.get("si")
    if not isinstance(crudas, dict) or not crudas:
        errores.append(f"Regla {id_regla}: 'si' debe ser un objeto no vacío {{hecho: condición}}")
    else:
        for hecho, spec in crudas.items():
            try:
                condiciones[hecho] = Condicion.desde(spec)
            except ValueError as e:
                errores.append(f"Regla {id_regla}: condición sobre '{hecho}': {e}")

    confianza = cruda.get("confianza")
    if isinstance(confianza, bool) or not isinstance(confianza, (int, float)) or not 0 < confianza <= 1:
        errores.append(f"Regla {id_regla}: 'confianza' debe ser un número en (0, 1]")

    recomendacion = cruda.get("recomendacion")
    if recomendacion is not None and not isinstance(recomendacion, str):
        errores.append(f"Regla {id_regla}: 'recomendacion' debe ser texto")

    advertencia = cruda.get("advertencia")
    if advertencia is not None:
        if not isinstance(advertencia, str) or not advertencia.strip():
            errores.append(f"Regla {id_regla}: 'advertencia' debe ser texto")
        elif recomendacion is None:
            errores.append(f"Regla {id_regla}: 'advertencia' solo tiene sentido junto a una 'recomendacion'")

    desconocidos = sorted(set(cruda) - CAMPOS_REGLA)
    if desconocidos:
        errores.append(f"Regla {id_regla}: campos desconocidos {desconocidos} "
                       f"(permitidos: {sorted(CAMPOS_REGLA)})")

    if len(errores) > antes:
        return None
    return Regla(
        id=cruda["id"],
        descripcion=cruda["descripcion"],
        condiciones=condiciones,
        conclusion=cruda["entonces"],
        confianza=float(confianza),
        recomendacion=recomendacion,
        advertencia=advertencia,
    )


def _construir_hecho(nombre: str, info: Any, errores: list[str]) -> Hecho | None:
    if not isinstance(info, dict):
        errores.append(f"El hecho '{nombre}' debe ser un objeto con su 'pregunta'")
        return None
    antes = len(errores)

    pregunta = info.get("pregunta")
    if not isinstance(pregunta, str) or not pregunta.strip():
        errores.append(f"El hecho '{nombre}' no tiene una 'pregunta' válida")

    tipo = info.get("tipo", SI_NO)
    if tipo not in TIPOS:
        errores.append(f"El hecho '{nombre}': 'tipo' debe ser uno de {list(TIPOS)}")
        return None

    ayuda = info.get("ayuda")
    if ayuda is not None and (not isinstance(ayuda, str) or not ayuda.strip()):
        errores.append(f"El hecho '{nombre}': 'ayuda' debe ser texto")

    opciones: tuple[tuple[str, str], ...] = ()
    if tipo == OPCION:
        crudas = info.get("opciones")
        if (not isinstance(crudas, dict) or len(crudas) < 2
                or not all(isinstance(e, str) and e.strip() for e in crudas.values())):
            errores.append(f"El hecho '{nombre}': 'opciones' debe ser un objeto con al menos "
                           "2 opciones {valor: etiqueta}")
        else:
            opciones = tuple(crudas.items())

    minimo, maximo = info.get("minimo"), info.get("maximo")
    unidad = info.get("unidad", "")
    if tipo == NUMERO:
        for campo, valor in (("minimo", minimo), ("maximo", maximo)):
            if valor is not None and not es_numero(valor):
                errores.append(f"El hecho '{nombre}': '{campo}' debe ser un número")
        if es_numero(minimo) and es_numero(maximo) and minimo >= maximo:
            errores.append(f"El hecho '{nombre}': 'minimo' debe ser menor que 'maximo'")
        if not isinstance(unidad, str):
            errores.append(f"El hecho '{nombre}': 'unidad' debe ser texto")

    desconocidos = sorted(set(info) - CAMPOS_HECHO[tipo])
    if desconocidos:
        errores.append(f"El hecho '{nombre}': campos no válidos para el tipo '{tipo}' {desconocidos} "
                       f"(permitidos: {sorted(CAMPOS_HECHO[tipo])})")

    if len(errores) > antes:
        return None
    return Hecho(nombre=nombre, pregunta=pregunta, tipo=tipo, opciones=opciones, unidad=unidad,
                 minimo=None if minimo is None else float(minimo),
                 maximo=None if maximo is None else float(maximo), ayuda=ayuda)


def _validar_condicion(id_regla: str, hecho: Hecho, condicion: Condicion) -> list[str]:
    """La condición debe corresponder al tipo del hecho y poder cumplirse."""
    if condicion.tipo != hecho.tipo:
        return [f"{id_regla}: la condición sobre '{hecho.nombre}' ({condicion.a_json()!r}) "
                f"no corresponde a un hecho de tipo '{hecho.tipo}'"]
    if hecho.tipo == OPCION:
        invalidas = sorted(condicion.esperado - set(hecho.valores_opcion))
        if invalidas:
            return [f"{id_regla}: '{hecho.nombre}' no tiene las opciones {invalidas} "
                    f"(opciones: {list(hecho.valores_opcion)})"]
    if hecho.tipo == NUMERO:
        inferiores = [n for op, n in condicion.esperado if op in (">", ">=")]
        superiores = [n for op, n in condicion.esperado if op in ("<", "<=")]
        if inferiores and superiores:
            abajo, arriba = max(inferiores), min(superiores)
            estricto = any(op in (">", "<") and n in (abajo, arriba) for op, n in condicion.esperado)
            if abajo > arriba or (abajo == arriba and estricto):
                return [f"{id_regla}: la condición sobre '{hecho.nombre}' "
                        f"({condicion.describir(hecho)}) nunca se puede cumplir"]
    return []


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
