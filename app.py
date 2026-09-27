"""
Interfaz web del sistema experto (Streamlit).

    streamlit run app.py

Igual que cli.py, solo presenta: toda la lógica vive en sistema_experto/.
"""

from __future__ import annotations

import json

import streamlit as st

from sistema_experto.conocimiento import cargar
from sistema_experto.modelo import NUMERO, OPCION, Valor, porcentaje
from sistema_experto.motor import (
    CONTRADICHA,
    CUMPLIDA,
    AnalisisRegla,
    Diagnostico,
    Pregunta,
    encadenar_hacia_adelante,
    encadenar_hacia_atras,
    exportar_red,
    hipotesis_abiertas,
    pregunta_sobre,
    siguiente_pregunta,
)
from sistema_experto.validacion import cargar_casos, evaluar
from sistema_experto.visualizacion import dot_razonamiento, dot_red

REPOSITORIO = "https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque"
ICONOS = {True: "✅", False: "❌", None: "❔"}

st.set_page_config(page_title="Diagnóstico de PC", page_icon="🖥️", layout="centered")


@st.cache_resource
def base_de_conocimiento():
    return cargar()


BASE = base_de_conocimiento()


@st.cache_data
def precision_medida() -> tuple[float, int, int]:
    """Precisión sobre los casos de referencia (se calcula una sola vez)."""
    evaluacion = evaluar(BASE, cargar_casos(BASE))
    return evaluacion.precision, sum(r.acierto for r in evaluacion.cubiertos), len(evaluacion.cubiertos)


# ── Estado de la sesión ───────────────────────────────────────

def respuestas() -> dict[str, Valor]:
    return st.session_state.setdefault("respuestas", {})


def responder(hecho: str, valor: Valor) -> None:
    respuestas()[hecho] = valor


def responder_numero(hecho: str, clave: str) -> None:
    """Toma el número escrito en el campo `clave` al momento del clic."""
    if st.session_state.get(clave) is not None:
        responder(hecho, float(st.session_state[clave]))


def deshacer() -> None:
    r = respuestas()
    if st.session_state.get("terminado"):
        st.session_state.terminado = False   # volver a la prueba que se saltó
    elif r:
        r.pop(next(reversed(r)))


def reiniciar() -> None:
    st.session_state.respuestas = {}
    st.session_state.terminado = False


def terminar() -> None:
    """Ver el diagnóstico sin hacer las pruebas de verificación que faltan."""
    st.session_state.terminado = True


def proxima_pregunta(r: dict[str, Valor]) -> Pregunta | None:
    if st.session_state.get("terminado"):
        return None
    if st.session_state.get("completo"):
        faltan = [h for h in BASE.preguntas if h not in r]
        return pregunta_sobre(BASE, r, faltan[0]) if faltan else None
    return siguiente_pregunta(BASE, r)


# ── Barra lateral ─────────────────────────────────────────────

def barra_lateral(r: dict[str, Valor]) -> None:
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
                # se comprueba el tipo antes: 1.0 == True, y un número no debe verse como "sí"
                icono = ICONOS[valor] if valor is None or isinstance(valor, bool) else "🔹"
                st.markdown(f"{icono} {BASE.preguntas[hecho]} **{BASE.formatear(hecho, valor)}**")

        st.divider()
        st.caption("⚠️ **Aviso:** este sistema orienta, no reemplaza a un técnico. "
                   "Apaga y desconecta el equipo antes de abrirlo.")
        precision, aciertos, total = precision_medida()
        st.caption(f"📊 **Precisión medida: {precision * 100:.0f} %** ({aciertos} de {total} "
                   f"[casos de referencia]({REPOSITORIO}/blob/main/casos/casos_referencia.json))")
        st.caption(f"[Código fuente en GitHub]({REPOSITORIO})")


# ── Consulta ──────────────────────────────────────────────────

def mostrar_pregunta(pregunta: Pregunta, r: dict[str, Valor]) -> None:
    abiertas = hipotesis_abiertas(BASE, r)
    diagnosticos = sum(1 for regla in BASE.reglas if regla.es_diagnostico)

    col1, col2 = st.columns(2)
    col1.metric("Pregunta", len(r) + 1)
    col2.metric("Hipótesis abiertas", f"{len(abiertas)} de {diagnosticos}")

    entrada = pregunta.entrada
    no_se = "No puedo hacerla" if entrada.prueba else "No sé"
    with st.container(border=True):
        if entrada.prueba:
            st.caption("🔧 **PRUEBA DE VERIFICACIÓN** · confirma o descarta el diagnóstico antes de reparar")
        st.subheader(pregunta.texto)
        if entrada.ayuda:
            st.caption(f"💡 {entrada.ayuda}")

        if entrada.tipo == OPCION:
            for valor, etiqueta in entrada.opciones:
                st.button(etiqueta, on_click=responder, args=(pregunta.hecho, valor),
                          key=f"opcion:{pregunta.hecho}:{valor}", width="stretch")
            st.button(no_se, on_click=responder, args=(pregunta.hecho, None), width="stretch")

        elif entrada.tipo == NUMERO:
            clave = f"numero:{pregunta.hecho}"
            st.number_input(
                f"Valor{' en ' + entrada.unidad if entrada.unidad else ''}",
                min_value=entrada.minimo, max_value=entrada.maximo, value=None,
                step=1.0, format="%g", key=clave, placeholder="Escribe el valor",
            )
            responder_col, no_se_col = st.columns(2)
            responder_col.button("Responder", on_click=responder_numero, args=(pregunta.hecho, clave),
                                 type="primary", disabled=st.session_state.get(clave) is None,
                                 width="stretch")
            no_se_col.button(no_se, on_click=responder, args=(pregunta.hecho, None), width="stretch")

        else:
            si, no, no_se_col = st.columns(3)
            si.button("Sí", on_click=responder, args=(pregunta.hecho, True),
                      type="primary", width="stretch")
            no.button("No", on_click=responder, args=(pregunta.hecho, False),
                      width="stretch")
            no_se_col.button(no_se, on_click=responder, args=(pregunta.hecho, None),
                             width="stretch")

    if entrada.prueba:
        st.button("⏭️ Ver el diagnóstico sin más pruebas", on_click=terminar)

    with st.expander("🤔 ¿Por qué me preguntas esto?"):
        if pregunta.hipotesis:
            st.markdown("Tu respuesta ayuda a confirmar o descartar:")
            for regla in pregunta.hipotesis:
                if regla.es_diagnostico:
                    detalle = f"confianza {regla.confianza * 100:.0f}%"
                else:
                    sentido = "en contra" if regla.en_contra else "a favor"
                    detalle = f"evidencia {sentido} de *{regla.conclusion}*"
                st.markdown(f"- **{regla.descripcion}** (`{regla.id}`, {detalle})")
        else:
            st.markdown("Ninguna hipótesis abierta depende de esta respuesta; "
                        "se pregunta porque activaste *Hacer todas las preguntas*.")


# ── Resultados ────────────────────────────────────────────────

def mostrar_resultado(r: dict[str, Valor]) -> None:
    inferencia = encadenar_hacia_adelante(BASE, r)
    diagnosticos = inferencia.diagnosticos

    st.caption(f"Consulta terminada en **{len(r)} de {len(BASE.preguntas)}** preguntas posibles.")
    tab_diag, tab_razon, tab_hipotesis, tab_red = st.tabs(
        ["🩺 Diagnóstico", "🔗 Razonamiento", "🔎 Explorar hipótesis", "🗺️ Base de conocimiento"]
    )

    with tab_diag:
        if not diagnosticos:
            st.info("No se llegó a ningún diagnóstico con suficiente certeza. "
                    "Prueba de nuevo o revisa la pestaña *Explorar hipótesis* para ver qué faltó.")
        else:
            principal, *otros = diagnosticos
            st.success(f"### {principal.descripcion}\nCerteza: **{porcentaje(principal.certeza)}**")
            for rec in principal.recomendaciones:
                st.markdown(f"👉 {rec}")
            for adv in principal.advertencias:
                st.warning(adv, icon="⚠️")
            mostrar_evidencia(principal)
            if otros:
                st.subheader("Otros diagnósticos posibles")
                for dg in otros:
                    st.progress(dg.certeza, text=f"{dg.descripcion} · {porcentaje(dg.certeza)}")
                    for rec in dg.recomendaciones:
                        st.caption(f"👉 {rec}")
                    for adv in dg.advertencias:
                        st.caption(f"⚠️ {adv}")
                    mostrar_evidencia(dg)
        if inferencia.descartados:
            st.subheader("Descartados por evidencia en contra")
            for dg in inferencia.descartados:
                motivos = "; ".join(d.regla.descripcion for d in dg.en_contra)
                st.markdown(f"~~{dg.descripcion}~~: {motivos}.")
        st.button("🔄 Nueva consulta", on_click=reiniciar, type="primary")

    with tab_razon:
        if not diagnosticos:
            st.info("Sin diagnóstico no hay cadena de razonamiento que mostrar.")
        else:
            elegido = st.selectbox(
                "Diagnóstico", diagnosticos, format_func=lambda dg: dg.descripcion,
            )
            st.graphviz_chart(dot_razonamiento(inferencia, elegido.hecho, BASE))
            for d in inferencia.justificacion(elegido.hecho):
                condiciones = ", ".join(f"`{h}` = {BASE.describir(h, c)}"
                                        for h, c in d.regla.condiciones.items())
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


def mostrar_evidencia(dg: Diagnostico) -> None:
    """Desglose de la certeza cuando varias reglas aportaron evidencia a favor o en contra."""
    if len(dg.disparos) < 2:
        return
    with st.expander(f"🧮 ¿Por qué {porcentaje(dg.certeza)} de certeza?"):
        for d in dg.disparos:
            icono = "➕" if d.certeza > 0 else "➖"
            sentido = "a favor" if d.certeza > 0 else "en contra"
            st.markdown(f"{icono} **{d.regla.descripcion}** (`{d.regla.id}`): {sentido}, "
                        f"{abs(d.certeza) * 100:.0f}%")
        st.caption("Las evidencias se combinan con el modelo de factores de certeza de MYCIN: "
                   "las que están a favor se refuerzan y las que están en contra restan.")


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
        lineas.append(f"{sangria}    - {simbolo} `{c.hecho}` = {BASE.describir(c.hecho, c.esperado)}")
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
