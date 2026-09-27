import itertools
import os
import random
import unittest

from sistema_experto.conocimiento import cargar
from sistema_experto.modelo import NUMERO, OPCION
from sistema_experto.motor import (
    encadenar_hacia_adelante,
    hipotesis_abiertas,
    pregunta_sobre,
    siguiente_pregunta,
)

BASE = cargar()
HECHOS = list(BASE.hechos)


def dominio(hecho: str) -> tuple:
    """
    Respuestas posibles de un hecho. Para los numéricos se usa un valor por cada región
    que delimitan los umbrales de las reglas (clases de equivalencia): dentro de una región
    todas las condiciones dan el mismo resultado. Los límites exactos de cada umbral se
    prueban aparte (test_motor: umbrales y rangos).
    """
    entrada = BASE.hechos[hecho]
    if entrada.tipo == OPCION:
        return entrada.valores_opcion
    if entrada.tipo == NUMERO:
        umbrales = sorted({n for r in BASE.reglas if hecho in r.condiciones
                           for _, n in r.condiciones[hecho].esperado})
        representantes = {umbrales[0] - 1, umbrales[-1] + 1}
        representantes |= {(a + b) / 2 for a, b in itertools.pairwise(umbrales)}
        return tuple(sorted(representantes))
    return (True, False)


DOMINIOS = {h: dominio(h) for h in HECHOS}

# Recorrer el árbol de decisión completo ya no es viable (más de 4000 millones de combinaciones
# de respuestas y creciendo con cada pregunta nueva). La propiedad se verifica con muestras
# aleatorias reproducibles: muchas en el CI (GitHub Actions define CI=true) o con
# PRUEBAS_EXTENSAS=1, y menos en local para que la suite sea rápida.
EXTENSAS = bool(os.environ.get("CI") or os.environ.get("PRUEBAS_EXTENSAS"))
MUESTRAS = 4000 if EXTENSAS else 300


def simular(verdad: dict) -> dict:
    """Consulta dinámica en la que el usuario responde según `verdad`."""
    respuestas = {}
    while (pregunta := siguiente_pregunta(BASE, respuestas)) is not None:
        assert pregunta.hecho not in respuestas, f"repitió la pregunta {pregunta.hecho}"
        respuestas[pregunta.hecho] = verdad[pregunta.hecho]
    return respuestas


def diagnosticos(respuestas: dict) -> set[str]:
    return {dg.hecho for dg in encadenar_hacia_adelante(BASE, respuestas).diagnosticos}


class TestConsultaDinamica(unittest.TestCase):
    def test_primera_pregunta_es_la_que_mas_hipotesis_abre(self):
        pregunta = siguiente_pregunta(BASE, {})
        self.assertEqual(pregunta.hecho, "enciende")
        confianzas = [r.confianza for r in pregunta.hipotesis]
        self.assertEqual(confianzas, sorted(confianzas, reverse=True))

    def test_si_no_enciende_bastan_cuatro_sintomas_y_las_pruebas(self):
        verdad = {h: False for h in HECHOS} | {
            "tipo_equipo": "escritorio", "interruptor_fuente_encendido": True, "prueba_otra_fuente": True}
        respuestas = simular(verdad)
        orden = list(respuestas)
        self.assertEqual(orden[:4], ["enciende", "tipo_equipo", "luces_led", "interruptor_fuente_encendido"])
        self.assertEqual(set(orden[4:]), {"prueba_otro_enchufe", "prueba_otra_fuente"})   # solo pruebas
        self.assertEqual(diagnosticos(respuestas), {"falla_fuente"})

    def test_la_pregunta_incluye_su_tipo_y_opciones(self):
        pregunta = pregunta_sobre(BASE, {}, "patron_pitidos")
        self.assertEqual(pregunta.entrada.tipo, OPCION)
        self.assertIn("uno_corto", pregunta.entrada.valores_opcion)
        self.assertTrue(pregunta.entrada.ayuda)

    def test_no_pregunta_por_hipotesis_descartadas(self):
        pregunta = siguiente_pregunta(BASE, {"enciende": True, "patron_pitidos": "repetidos"})
        ids = {r.id for r in pregunta.hipotesis}
        self.assertTrue(ids.isdisjoint({"R01", "R11", "R03", "R12", "R13", "R10"}), ids)

    def test_no_se_no_se_vuelve_a_preguntar(self):
        respuestas = {"enciende": None}
        while (pregunta := siguiente_pregunta(BASE, respuestas)) is not None:
            self.assertNotEqual(pregunta.hecho, "enciende")
            respuestas[pregunta.hecho] = None
        # con todo "no sé" ninguna hipótesis puede avanzar
        self.assertEqual(hipotesis_abiertas(BASE, respuestas), [])
        self.assertEqual(diagnosticos(respuestas), set())

    def test_no_se_deja_el_hecho_desconocido(self):
        inferencia = encadenar_hacia_adelante(BASE, {"enciende": None, "luces_led": False})
        self.assertIsNone(inferencia.hechos.valor("enciende"))
        self.assertEqual(inferencia.diagnosticos, [])

    def test_pregunta_sin_hipotesis_interesadas(self):
        pregunta = pregunta_sobre(BASE, {"enciende": False}, "disco_al_100")
        self.assertEqual(pregunta.hipotesis, ())

    def test_nunca_pierde_un_diagnostico_por_preguntar_menos(self):
        """
        Propiedad central de la consulta dinámica: para cualquier equipo, preguntar solo lo
        relevante da los mismos diagnósticos que preguntar todo. Se verifica con equipos
        generados al azar (semilla fija, reproducible) en todo el dominio de respuestas.
        """
        azar = random.Random(2026)
        for _ in range(MUESTRAS):
            verdad = {h: azar.choice(DOMINIOS[h]) for h in HECHOS}
            self.assertEqual(diagnosticos(simular(verdad)), diagnosticos(verdad), verdad)

    def test_equivale_a_preguntar_todo_con_no_se(self):
        azar = random.Random(42)
        for _ in range(MUESTRAS):
            verdad = {h: azar.choice((*DOMINIOS[h], None)) for h in HECHOS}
            self.assertEqual(diagnosticos(simular(verdad)), diagnosticos(verdad), verdad)


if __name__ == "__main__":
    unittest.main()
