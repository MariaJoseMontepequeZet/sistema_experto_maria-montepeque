"""
Interfaz de usuario por consola. Toda la entrada/salida vive aquí;
el motor solo devuelve datos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .conocimiento import RUTA_POR_DEFECTO, ErrorDeConocimiento, cargar
from .modelo import BaseDeConocimiento
from .motor import (
    CONTRADICHA,
    CUMPLIDA,
    AnalisisRegla,
    Inferencia,
    encadenar_hacia_adelante,
    encadenar_hacia_atras,
    exportar_red,
)

LINEA_GRUESA = "━" * 55
LINEA_FINA = "  " + "─" * 51


def preguntar_si_no(pregunta: str) -> bool:
    while True:
        resp = input(f"  {pregunta} [s/n]: ").strip().lower()
        if resp in ("s", "n"):
            return resp == "s"
        print("  ⚠ Por favor escribe s o n.")


def formatear_condiciones(condiciones: dict[str, bool]) -> str:
    return ", ".join(f"{h}={'sí' if v else 'no'}" for h, v in condiciones.items())


def mostrar_inferencia(inferencia: Inferencia, mostrar_todos: bool) -> None:
    print()
    print(LINEA_GRUESA)
    print("  MOTOR DE INFERENCIA")
    print(LINEA_GRUESA)
    afirmados = sorted(h for h, v in inferencia.hechos.valores.items()
                       if v and inferencia.hechos.origen[h] == ["usuario"])
    print(f"  Síntomas confirmados: {', '.join(afirmados) or '—'}")
    print()

    diagnosticos = inferencia.diagnosticos
    if not diagnosticos:
        print("  ⚠ No se encontraron reglas aplicables.")
        print("  Considera revisar las respuestas o ampliar la base de conocimiento.")
        print(LINEA_GRUESA)
        return

    if mostrar_todos:
        print("  RANKING COMPLETO DE DIAGNÓSTICOS")
        print(LINEA_FINA)
        for i, dg in enumerate(diagnosticos, 1):
            print(f"  #{i} {dg.descripcion}  ({dg.certeza * 100:.0f}%)")
            for rec in dg.recomendaciones:
                print(f"      → {rec}")
            print()
    else:
        dg = diagnosticos[0]
        print("  DIAGNÓSTICO PRINCIPAL")
        print(LINEA_FINA)
        print(f"  {dg.descripcion}")
        for rec in dg.recomendaciones:
            print(f"  Recomendación: {rec}")
        print(f"  Certeza:       {dg.certeza * 100:.0f}%")
        print()

    principal = diagnosticos[0]
    print("  TRAZABILIDAD DEL RAZONAMIENTO (diagnóstico principal)")
    print(LINEA_FINA)
    for d in inferencia.justificacion(principal.hecho):
        print(f"  Ciclo {d.ciclo}: [{d.regla.id}] {d.regla.descripcion}")
        print(f"      SI {formatear_condiciones(d.regla.condiciones)}")
        print(f"      ENTONCES {d.regla.conclusion}  ({d.certeza * 100:.0f}%)")
    if not mostrar_todos and len(diagnosticos) > 1:
        otros = [f"{dg.descripcion} ({dg.certeza * 100:.0f}%)" for dg in diagnosticos[1:]]
        print(f"  Otros diagnósticos con menor certeza: {'; '.join(otros)}")
    print(LINEA_GRUESA)


def mostrar_analisis(analisis: AnalisisRegla, nivel: int = 0) -> None:
    sangria = "  " + "    " * nivel
    r = analisis.regla
    if analisis.se_activa:
        estado = "✓ SÍ"
    elif analisis.descartada:
        estado = "✗ NO (hay síntomas que la contradicen)"
    else:
        estado = "… AÚN NO (faltan síntomas)"
    print(f"{sangria}Regla objetivo : {r.id} — {r.descripcion} ({r.confianza * 100:.0f}%)")
    print(f"{sangria}¿Se activa?    : {estado}")
    for c in analisis.condiciones:
        simbolo = {CUMPLIDA: "✓", CONTRADICHA: "✗"}.get(c.estado, "?")
        esperado = "sí" if c.esperado else "no"
        print(f"{sangria}  {simbolo} {c.hecho} = {esperado}  [{c.estado}]")
        for sub in c.subobjetivos:
            mostrar_analisis(sub, nivel + 1)
    if nivel == 0 and analisis.por_preguntar:
        print(f"{sangria}Falta confirmar: {', '.join(analisis.por_preguntar)}")


def consultar(base: BaseDeConocimiento, ruta_exportacion: Path) -> None:
    print()
    print("=" * 55)
    print(f"  SISTEMA EXPERTO: {base.nombre}")
    print("  Responde s (sí) o n (no) a cada pregunta")
    print("=" * 55)
    print()

    respuestas = {hecho: preguntar_si_no(p) for hecho, p in base.preguntas.items()}

    print()
    mostrar_todos = preguntar_si_no("¿Ver ranking completo de diagnósticos?")
    mostrar_inferencia(encadenar_hacia_adelante(base, respuestas), mostrar_todos)

    print()
    print("  OPCIONES ADICIONALES")
    print(LINEA_FINA)

    if preguntar_si_no("¿Ejecutar encadenamiento hacia atrás?"):
        print()
        print("  IDs disponibles: " + ", ".join(r.id for r in base.reglas))
        meta = input("  Ingresa el ID de la regla o el hecho a analizar (ej. R07): ")
        print()
        print(LINEA_GRUESA)
        print("  ENCADENAMIENTO HACIA ATRÁS")
        print(LINEA_GRUESA)
        try:
            for analisis in encadenar_hacia_atras(base, meta, respuestas):
                mostrar_analisis(analisis)
                print()
        except LookupError as e:
            print(f"  ⚠ {e}")
        print(LINEA_GRUESA)

    print()
    if preguntar_si_no("¿Exportar red de inferencia a JSON?"):
        grafo = exportar_red(base)
        with open(ruta_exportacion, "w", encoding="utf-8") as f:
            json.dump(grafo, f, ensure_ascii=False, indent=2)
        print(f"\n  ✓ Red exportada a: {ruta_exportacion}")
        print(f"    Nodos  : {len(grafo['nodos'])}")
        print(f"    Aristas: {len(grafo['aristas'])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sistema_experto",
        description="Sistema experto basado en reglas para diagnóstico.",
    )
    parser.add_argument("--conocimiento", type=Path, default=RUTA_POR_DEFECTO,
                        help="archivo JSON con la base de conocimiento")
    parser.add_argument("--salida", type=Path, default=Path("red_inferencia.json"),
                        help="ruta donde exportar la red de inferencia")
    args = parser.parse_args(argv)

    try:
        base = cargar(args.conocimiento)
    except FileNotFoundError:
        print(f"No se encontró la base de conocimiento: {args.conocimiento}", file=sys.stderr)
        return 1
    except (ErrorDeConocimiento, json.JSONDecodeError) as e:
        print(e, file=sys.stderr)
        return 1

    try:
        consultar(base, args.salida)
    except (KeyboardInterrupt, EOFError):
        print("\n  Consulta cancelada.")
        return 130
    return 0
