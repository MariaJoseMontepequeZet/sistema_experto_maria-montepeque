"""
Diagramas en formato DOT (Graphviz) de la base de conocimiento y del
razonamiento de una consulta. Solo genera texto: cualquier interfaz
(Streamlit, un visor de Graphviz, etc.) puede dibujarlo.
"""

from __future__ import annotations

from .modelo import BaseDeConocimiento
from .motor import Inferencia, exportar_red

# Colores legibles tanto en tema claro como oscuro (relleno claro, texto oscuro)
ESTILOS = {
    "si":          'shape=box, style="rounded,filled", fillcolor="#d3f9d8", color="#2b8a3e"',
    "no":          'shape=box, style="rounded,filled", fillcolor="#ffe3e3", color="#c92a2a"',
    "desconocido": 'shape=box, style="rounded,filled,dashed", fillcolor="#f1f3f5", color="#868e96"',
    "entrada":     'shape=box, style="rounded,filled", fillcolor="#f1f3f5", color="#868e96"',
    "regla":       'shape=ellipse, style=filled, fillcolor="#d0ebff", color="#1864ab"',
    "intermedio":  'shape=box, style="rounded,filled", fillcolor="#fff3bf", color="#e67700"',
    "diagnostico": 'shape=box, style="rounded,filled,bold", fillcolor="#e5dbff", color="#5f3dc4"',
}

CABECERA = [
    "digraph G {",
    '  graph [rankdir=LR, bgcolor="transparent", nodesep=0.25, ranksep=0.6];',
    '  node [fontname="Helvetica", fontsize=11, fontcolor="#212529"];',
    '  edge [color="#868e96", fontname="Helvetica", fontsize=9, fontcolor="#868e96"];',
]


def dot_razonamiento(inferencia: Inferencia, hecho: str) -> str:
    """Cadena de reglas que llevó a `hecho`: respuestas → reglas → hechos derivados."""
    hechos = inferencia.hechos
    lineas = list(CABECERA)
    declarados: set[str] = set()

    def nodo(id_nodo: str, etiqueta: str, estilo: str) -> None:
        if id_nodo not in declarados:
            declarados.add(id_nodo)
            lineas.append(f"  {_id(id_nodo)} [label={_texto(etiqueta)}, {ESTILOS[estilo]}];")

    for d in inferencia.justificacion(hecho):
        regla = d.regla
        id_regla = f"regla:{regla.id}"
        nodo(id_regla, f"{regla.id}\n{regla.descripcion}\n{d.certeza * 100:.0f}%", "regla")
        for condicion, esperado in regla.condiciones.items():
            if condicion in hechos.origen and hechos.origen[condicion] != ["usuario"]:
                nodo(condicion, condicion, "intermedio")
            else:
                valor = hechos.valor(condicion)
                nodo(condicion, f"{condicion} = {'sí' if valor else 'no'}", "si" if valor else "no")
            lineas.append(f"  {_id(condicion)} -> {_id(id_regla)};")
        estilo = "diagnostico" if regla.es_diagnostico else "intermedio"
        nodo(regla.conclusion, regla.conclusion, estilo)
        lineas.append(f"  {_id(id_regla)} -> {_id(regla.conclusion)};")

    lineas.append("}")
    return "\n".join(lineas)


def dot_red(base: BaseDeConocimiento) -> str:
    """Red de inferencia completa: hechos de entrada, reglas, intermedios y diagnósticos."""
    red = exportar_red(base)
    lineas = list(CABECERA)
    for n in red["nodos"]:
        if n["tipo"] == "regla":
            etiqueta = f"{n['id']}\n{n['confianza'] * 100:.0f}%"
            id_nodo = f"regla:{n['id']}"
        else:
            etiqueta = n["id"]
            id_nodo = n["id"]
        lineas.append(f"  {_id(id_nodo)} [label={_texto(etiqueta)}, "
                      f"tooltip={_texto(n['etiqueta'])}, {ESTILOS[n['tipo']]}];")

    reglas = {r.id for r in base.reglas}
    for a in red["aristas"]:
        origen = f"regla:{a['origen']}" if a["origen"] in reglas else a["origen"]
        destino = f"regla:{a['destino']}" if a["destino"] in reglas else a["destino"]
        atributos = ' [style=dashed, label="no"]' if a.get("valor") is False else ""
        lineas.append(f"  {_id(origen)} -> {_id(destino)}{atributos};")

    lineas.append("}")
    return "\n".join(lineas)


def _texto(valor: str) -> str:
    escapado = valor.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escapado}"'


def _id(valor: str) -> str:
    return _texto(valor)
