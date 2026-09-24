import itertools
import random
import unittest

from sistema_experto.conocimiento import cargar
from sistema_experto.motor import (
    encadenar_hacia_adelante,
    hipotesis_abiertas,
    pregunta_sobre,
    siguiente_pregunta,
)

BASE = cargar()
HECHOS = list(BASE.preguntas)


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

    def test_si_no_enciende_solo_hace_dos_preguntas(self):
        respuestas = simular({h: False for h in HECHOS})
        self.assertEqual(list(respuestas), ["enciende", "luces_led"])
        self.assertEqual(diagnosticos(respuestas), {"falla_fuente"})

    def test_no_pregunta_por_hipotesis_descartadas(self):
        pregunta = siguiente_pregunta(BASE, {"enciende": True, "pitidos_arranque": True})
        ids = {r.id for r in pregunta.hipotesis}
        self.assertNotIn("R01", ids)   # requiere enciende = no
        self.assertNotIn("R03", ids)   # requiere pitidos = no
        self.assertNotIn("R10", ids)

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

    def test_equivale_a_preguntar_todo_en_todas_las_combinaciones(self):
        """
        Nunca se pierde un diagnóstico por preguntar menos. Recorre el árbol de
        decisión de la consulta dinámica y, en cada hoja, comprueba que para
        CUALQUIER valor de los hechos no preguntados el resultado sería el mismo.
        En total cubre las 2^14 combinaciones posibles de respuestas.
        """
        casos = 0
        pendientes = [{}]
        while pendientes:
            respuestas = pendientes.pop()
            pregunta = siguiente_pregunta(BASE, respuestas)
            if pregunta is not None:
                for valor in (True, False):
                    pendientes.append({**respuestas, pregunta.hecho: valor})
                continue
            esperado = diagnosticos(respuestas)
            sin_preguntar = [h for h in HECHOS if h not in respuestas]
            for valores in itertools.product((False, True), repeat=len(sin_preguntar)):
                verdad = {**respuestas, **dict(zip(sin_preguntar, valores))}
                self.assertEqual(esperado, diagnosticos(verdad), verdad)
                casos += 1
        self.assertEqual(casos, 2 ** len(HECHOS))

    def test_equivale_a_preguntar_todo_con_no_se(self):
        azar = random.Random(42)
        for _ in range(300):
            verdad = {h: azar.choice((True, False, None)) for h in HECHOS}
            self.assertEqual(diagnosticos(simular(verdad)), diagnosticos(verdad), verdad)


if __name__ == "__main__":
    unittest.main()
