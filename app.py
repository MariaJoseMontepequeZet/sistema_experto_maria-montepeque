"""
Interfaz web del sistema experto (Streamlit).

    streamlit run app.py

Igual que cli.py, solo presenta: toda la lógica vive en sistema_experto/.
"""

from __future__ import annotations

import json

import streamlit as st

from sistema_experto.conocimiento import cargar
from sistema_experto.motor import (
    CONTRADICHA,
    CUMPLIDA,
    AnalisisRegla,
    Pregunta,
    encadenar_hacia_adelante,
    encadenar_hacia_atras,
    exportar_red,
    hipotesis_abiertas,
    pregunta_sobre,
    siguiente_pregunta,
)
from sistema_experto.visualizacion import dot_razonamiento, dot_red

REPOSITORIO = "https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque"
VALORES = {True: "✅ sí", False: "❌ no", None: "❔ no sé"}

st.set_page_config(page_title="Diagnóstico de PC", page_icon="🖥️", layout="centered")


@st.cache_resource
def base_de_conocimiento():
    return cargar()


BASE = base_de_conocimiento()


# ── Estado de la sesión ───────────────────────────────────────

def respuestas() -> dict[str, bool | None]:
    return st.session_state.setdefault("respuestas", {})


def responder(hecho: str, valor: bool | None) -> None:
    respuestas()[hecho] = valor


def deshacer() -> None:
    r = respuestas()
    if r:
        r.pop(next(reversed(r)))


def reiniciar() -> None:
    st.session_state.respuestas = {}


def proxima_pregunta(r: dict[str, bool | None]) -> Pregunta | None:
    if st.session_state.get("completo"):
        faltan = [h for h in BASE.preguntas if h not in r]
        return pregunta_sobre(BASE, r, faltan[0]) if faltan else None
    return siguiente_pregunta(BASE, r)


# ── Barra lateral ─────────────────────────────────────────────

def barra_lateral(r: dict[str, bool | None]) -> None:
    with st.sidebar:
        st.header("🧠 ¿Cómo funciona?")
        st.markdown(
            "Un **sistema experto** separa el conocimiento (reglas escritas por un técnico) "
            "del **motor de inferencia** que las aplica.\n\n"
            "Solo te pregunta lo que sirve para las hipótesis que siguen abiertas y, al final, "
            "te muestra el diagnóstico y **por qué** llegó a él."
        )
        st.toggle("Hacer todas las preguntas", key="completo",
                  help="Desactivado: consulta dinámica, solo preguntas relevantes.")

        col1, col2 = st.columns(2)
        col1.button("↩️ Deshacer", on_click=deshacer, disabled=not r, width="stretch")
        col2.button("🔄 Reiniciar", on_click=reiniciar, disabled=not r, width="stretch")

        if r:
            st.subheader("Tus respuestas")
            for hecho, valor in r.items():
                st.markdown(f"{VALORES[valor]} · {BASE.preguntas[hecho]}")

        st.divider()
        st.caption(f"[Código fuente en GitHub]({REPOSITORIO})")


# ── Consulta ──────────────────────────────────────────────────

def mostrar_pregunta(pregunta: Pregunta, r: dict[str, bool | None]) -> None:
    abiertas = hipotesis_abiertas(BASE, r)
    diagnosticos = sum(1 for regla in BASE.reglas if regla.es_diagnostico)

    col1, col2 = st.columns(2)
    col1.metric("Pregunta", len(r) + 1)
    col2.metric("Hipótesis abiertas", f"{len(abiertas)} de {diagnosticos}")

    with st.container(border=True):
        st.subheader(pregunta.texto)
        si, no, no_se = st.columns(3)
        si.button("Sí", on_click=responder, args=(pregunta.hecho, True),
                  type="primary", width="stretch")
        no.button("No", on_click=responder, args=(pregunta.hecho, False),
                  width="stretch")
        no_se.button("No sé", on_click=responder, args=(pregunta.hecho, None),
                     width="stretch")

    with st.expander("🤔 ¿Por qué me preguntas esto?"):
        if pregunta.hipotesis:
            st.markdown("Tu respuesta ayuda a confirmar o descartar:")
            for regla in pregunta.hipotesis:
                st.markdown(f"- **{regla.descripcion}** (`{regla.id}`, confianza "
                            f"{regla.confianza * 100:.0f}%)")
        else:
            st.markdown("Ninguna hipótesis abierta depende de esta respuesta; "
                        "se pregunta porque activaste *Hacer todas las preguntas*.")


# ── Resultados ────────────────────────────────────────────────

def mostrar_resultado(r: dict[str, bool | None]) -> None:
    inferencia = encadenar_hacia_adelante(BASE, r)
    diagnosticos = inferencia.diagnosticos

    st.caption(f"Consulta terminada en **{len(r)} de {len(BASE.preguntas)}** preguntas posibles.")
    tab_diag, tab_razon, tab_hipotesis, tab_red = st.tabs(
        ["🩺 Diagnóstico", "🔗 Razonamiento", "🔎 Explorar hipótesis", "🗺️ Base de conocimiento"]
    )

    with tab_diag:
        if not diagnosticos:
            st.info("No se encontró ningún diagnóstico con estas respuestas. "
                    "Prueba de nuevo o revisa la pestaña *Explorar hipótesis* para ver qué faltó.")
        else:
            principal, *otros = diagnosticos
            st.success(f"### {principal.descripcion}\nCerteza: **{principal.certeza * 100:.0f}%**")
            for rec in principal.recomendaciones:
                st.markdown(f"👉 {rec}")
            if otros:
                st.subheader("Otros diagnósticos posibles")
                for dg in otros:
                    st.progress(dg.certeza, text=f"{dg.descripcion} · {dg.certeza * 100:.0f}%")
                    for rec in dg.recomendaciones:
                        st.caption(f"👉 {rec}")
        st.button("🔄 Nueva consulta", on_click=reiniciar, type="primary")

    with tab_razon:
        if not diagnosticos:
            st.info("Sin diagnóstico no hay cadena de razonamiento que mostrar.")
        else:
            elegido = st.selectbox(
                "Diagnóstico", diagnosticos, format_func=lambda dg: dg.descripcion,
            )
            st.graphviz_chart(dot_razonamiento(inferencia, elegido.hecho))
            for d in inferencia.justificacion(elegido.hecho):
                condiciones = ", ".join(f"`{h}` = {'sí' if v else 'no'}"
                                        for h, v in d.regla.condiciones.items())
                st.markdown(f"**Ciclo {d.ciclo} · [{d.regla.id}] {d.regla.descripcion}**  \n"
                            f"SI {condiciones} ENTONCES `{d.regla.conclusion}` "
                            f"({d.certeza * 100:.0f}%)")

    with tab_hipotesis:
        st.markdown("Encadenamiento **hacia atrás**: elige una hipótesis y mira qué la "
                    "confirma, qué la contradice y qué faltaría saber.")
        candidatas = [regla for regla in BASE.reglas if regla.es_diagnostico]
        meta = st.selectbox("Hipótesis", candidatas,
                            format_func=lambda regla: f"{regla.descripcion} ({regla.id})")
        for analisis in encadenar_hacia_atras(BASE, meta.id, r):
            st.markdown("\n".join(lineas_analisis(analisis)))
            faltan = [h for h in analisis.por_preguntar if h not in r]
            if faltan:
                st.caption("Faltaría confirmar: " + ", ".join(f"`{h}`" for h in faltan))

    with tab_red:
        st.markdown("Todas las reglas: 🟦 reglas · 🟨 hechos intermedios · 🟪 diagnósticos. "
                    "Las flechas punteadas indican una condición negada.")
        st.graphviz_chart(dot_red(BASE), width="stretch")
        st.download_button(
            "⬇️ Descargar red de inferencia (JSON)",
            json.dumps(exportar_red(BASE), ensure_ascii=False, indent=2),
            file_name="red_inferencia.json",
            mime="application/json",
        )


def lineas_analisis(analisis: AnalisisRegla, nivel: int = 0) -> list[str]:
    sangria = "    " * nivel
    if analisis.se_activa:
        estado = "✅ se activa"
    elif analisis.descartada:
        estado = "❌ descartada"
    else:
        estado = "⏳ faltan datos"
    regla = analisis.regla
    lineas = [f"{sangria}- **{regla.descripcion}** (`{regla.id}`, "
              f"{regla.confianza * 100:.0f}%) — {estado}"]
    for c in analisis.condiciones:
        simbolo = {CUMPLIDA: "✅", CONTRADICHA: "❌"}.get(c.estado, "❔")
        lineas.append(f"{sangria}    - {simbolo} `{c.hecho}` = {'sí' if c.esperado else 'no'}")
        for sub in c.subobjetivos:
            lineas.extend(lineas_analisis(sub, nivel + 2))
    return lineas


# ── Página ────────────────────────────────────────────────────

st.title("🖥️ Diagnóstico de PC")
st.caption("Sistema experto basado en reglas · encadenamiento hacia adelante y hacia atrás")

r = respuestas()
barra_lateral(r)
pregunta = proxima_pregunta(r)
if pregunta is not None:
    mostrar_pregunta(pregunta, r)
else:
    mostrar_resultado(r)
