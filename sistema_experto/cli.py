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
from .modelo import NUMERO, OPCION, ORIGEN_USUARIO, BaseDeConocimiento, Condicion, Hecho, Valor
from .motor import (
    CONTRADICHA,
    CUMPLIDA,
    AnalisisRegla,
    Inferencia,
    Pregunta,
    encadenar_hacia_adelante,
    encadenar_hacia_atras,
    exportar_red,
    pregunta_sobre,
    siguiente_pregunta,
)

AVISO = ("Aviso: este sistema orienta, no reemplaza a un técnico.\n"
         "  Apaga y desconecta el equipo antes de abrirlo.")

LINEA_GRUESA = "━" * 55
LINEA_FINA = "  " + "─" * 51

RESPUESTAS_SINTOMA = {"s": True, "n": False, "ns": None}


def preguntar_si_no(pregunta: str) -> bool:
    while True:
        resp = input(f"  {pregunta} [s/n]: ").strip().lower()
        if resp in ("s", "n"):
            return resp == "s"
        print("  ⚠ Por favor escribe s o n.")


def preguntar_sintoma(numero: int, pregunta: Pregunta) -> Valor:
    """
    Pide la respuesta según el tipo de pregunta:
      sí/no  → s, n        opción → su número        número → el valor
    En todos los casos: ns = no sé, ? = explica por qué se hace la pregunta.
    """
    entrada = pregunta.entrada or Hecho(pregunta.hecho, pregunta.texto)
    print(f"  {numero}. {pregunta.texto}")
    if entrada.tipo == OPCION:
        for i, (_, etiqueta) in enumerate(entrada.opciones, 1):
            print(f"       {i}) {etiqueta}")
        formato = f"1-{len(entrada.opciones)}/ns/?"
    elif entrada.tipo == NUMERO:
        formato = f"número{' en ' + entrada.unidad if entrada.unidad else ''}/ns/?"
    else:
        formato = "s/n/ns/?"

    while True:
        resp = input(f"     [{formato}]: ").strip().lower()
        if resp == "ns":
            return None
        if resp == "?":
            explicar_pregunta(pregunta)
            continue
        valor = interpretar_respuesta(entrada, resp)
        if valor is not None:
            return valor
        print(f"  ⚠ Respuesta no válida. Escribe {formato.replace('/', ', ')} "
              "(ns = no sé, ? = ¿por qué me preguntas esto?).")


def interpretar_respuesta(entrada: Hecho, texto: str) -> Valor:
    """Convierte lo que escribió el usuario al valor del hecho, o None si no es válido."""
    if entrada.tipo == OPCION:
        if texto.isdigit() and 1 <= int(texto) <= len(entrada.opciones):
            return entrada.opciones[int(texto) - 1][0]
        return None
    if entrada.tipo == NUMERO:
        try:
            valor = float(texto.replace(",", "."))
        except ValueError:
            return None
        return valor if entrada.admite(valor) else None
    return RESPUESTAS_SINTOMA.get(texto) if texto in ("s", "n") else None


def explicar_pregunta(pregunta: Pregunta) -> None:
    if pregunta.entrada and pregunta.entrada.ayuda:
        print(f"     💡 {pregunta.entrada.ayuda}")
    if not pregunta.hipotesis:
        print("     Ninguna hipótesis abierta depende de esta respuesta;"
              " se pregunta porque estás en modo --completo.")
        return
    print("     Pregunto esto porque ayuda a confirmar o descartar:")
    for regla in pregunta.hipotesis:
        print(f"       • [{regla.id}] {regla.descripcion} ({regla.confianza * 100:.0f}%)")


def recolectar_respuestas(base: BaseDeConocimiento, completo: bool) -> dict[str, Valor]:
    """
    Modo dinámico: pregunta solo lo que ayuda a alguna hipótesis que sigue abierta.
    Modo completo: hace todas las preguntas en el orden del archivo.
    """
    respuestas: dict[str, Valor] = {}
    while True:
        if completo:
            faltantes = [h for h in base.preguntas if h not in respuestas]
            pregunta = pregunta_sobre(base, respuestas, faltantes[0]) if faltantes else None
        else:
            pregunta = siguiente_pregunta(base, respuestas)
        if pregunta is None:
            return respuestas
        respuestas[pregunta.hecho] = preguntar_sintoma(len(respuestas) + 1, pregunta)


def formatear_condiciones(base: BaseDeConocimiento, condiciones: dict[str, Condicion]) -> str:
    return ", ".join(f"{h}={base.describir(h, c)}" for h, c in condiciones.items())


def formatear_respuestas(base: BaseDeConocimiento, respuestas: dict[str, Valor]) -> str:
    return ", ".join(f"{h}={base.formatear(h, v)}" for h, v in respuestas.items())


def mostrar_inferencia(base: BaseDeConocimiento, inferencia: Inferencia, mostrar_todos: bool,
                       no_sabe: list[str] | None = None) -> None:
    print()
    print(LINEA_GRUESA)
    print("  MOTOR DE INFERENCIA")
    print(LINEA_GRUESA)
    del_usuario = {h: v for h, v in inferencia.hechos.valores.items()
                   if inferencia.hechos.origen[h] == [ORIGEN_USUARIO]}
    print(f"  Respuestas: {formatear_respuestas(base, del_usuario) or '—'}")
    if no_sabe:
        print(f"  Respondidos con 'no sé': {', '.join(no_sabe)}")
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
            for adv in dg.advertencias:
                print(f"      ⚠ {adv}")
            print()
    else:
        dg = diagnosticos[0]
        print("  DIAGNÓSTICO PRINCIPAL")
        print(LINEA_FINA)
        print(f"  {dg.descripcion}")
        for rec in dg.recomendaciones:
            print(f"  Recomendación: {rec}")
        print(f"  Certeza:       {dg.certeza * 100:.0f}%")
        for adv in dg.advertencias:
            print(f"  ⚠ Precaución:  {adv}")
        print()

    principal = diagnosticos[0]
    print("  TRAZABILIDAD DEL RAZONAMIENTO (diagnóstico principal)")
    print(LINEA_FINA)
    for d in inferencia.justificacion(principal.hecho):
        print(f"  Ciclo {d.ciclo}: [{d.regla.id}] {d.regla.descripcion}")
        print(f"      SI {formatear_condiciones(base, d.regla.condiciones)}")
        print(f"      ENTONCES {d.regla.conclusion}  ({d.certeza * 100:.0f}%)")
    if not mostrar_todos and len(diagnosticos) > 1:
        otros = [f"{dg.descripcion} ({dg.certeza * 100:.0f}%)" for dg in diagnosticos[1:]]
        print(f"  Otros diagnósticos con menor certeza: {'; '.join(otros)}")
    print(LINEA_GRUESA)


def mostrar_analisis(base: BaseDeConocimiento, analisis: AnalisisRegla, nivel: int = 0) -> None:
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
        print(f"{sangria}  {simbolo} {c.hecho} = {base.describir(c.hecho, c.esperado)}  [{c.estado}]")
        for sub in c.subobjetivos:
            mostrar_analisis(base, sub, nivel + 1)
    if nivel == 0 and analisis.por_preguntar:
        print(f"{sangria}Falta confirmar: {', '.join(analisis.por_preguntar)}")


def consultar(base: BaseDeConocimiento, ruta_exportacion: Path, completo: bool = False) -> None:
    print()
    print("=" * 55)
    print(f"  SISTEMA EXPERTO: {base.nombre}")
    print("  Responde: s (sí) · n (no) · el número de la opción · ns (no sé)")
    print("  Escribe ? para saber por qué se hace una pregunta")
    print("-" * 55)
    print(f"  {AVISO}")
    print("=" * 55)
    print()

    respuestas = recolectar_respuestas(base, completo)
    print()
    print(f"  Se hicieron {len(respuestas)} de {len(base.preguntas)} preguntas posibles.")

    print()
    mostrar_todos = preguntar_si_no("¿Ver ranking completo de diagnósticos?")
    no_sabe = [h for h, v in respuestas.items() if v is None]
    mostrar_inferencia(base, encadenar_hacia_adelante(base, respuestas), mostrar_todos, no_sabe)

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
                mostrar_analisis(base, analisis)
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
    parser.add_argument("--completo", action="store_true",
                        help="hacer todas las preguntas en lugar de solo las relevantes")
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
        consultar(base, args.salida, args.completo)
    except (KeyboardInterrupt, EOFError):
        print("\n  Consulta cancelada.")
        return 130
    return 0
