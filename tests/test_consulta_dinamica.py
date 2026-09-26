import itertools
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
    """Respuestas posibles de un hecho. Para los numéricos basta con el valor de cada umbral
    usado en las reglas y uno justo por debajo: es donde puede cambiar el resultado."""
    entrada = BASE.hechos[hecho]
    if entrada.tipo == OPCION:
        return entrada.valores_opcion
    if entrada.tipo == NUMERO:
        umbrales = {n for r in BASE.reglas if hecho in r.condiciones
                    for _, n in r.condiciones[hecho].esperado}
        return tuple(sorted({u + d for u in umbrales for d in (-0.5, 0)}))
    return (True, False)


DOMINIOS = {h: dominio(h) for h in HECHOS}


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

    def test_si_no_enciende_solo_hace_tres_preguntas(self):
        verdad = {h: False for h in HECHOS} | {"tipo_equipo": "escritorio"}
        respuestas = simular(verdad)
        self.assertEqual(list(respuestas), ["enciende", "tipo_equipo", "luces_led"])
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
        Recorre el árbol de decisión COMPLETO de la consulta dinámica (cada rama con todas
        las respuestas posibles) y, en cada hoja, comprueba que el resultado sería el mismo
        para las respuestas que no se preguntaron: todas si son pocas combinaciones, o una
        muestra reproducible si son muchas.
        """
        azar = random.Random(2026)
        hojas = comprobaciones = 0
        pendientes = [{}]
        while pendientes:
            respuestas = pendientes.pop()
            pregunta = siguiente_pregunta(BASE, respuestas)
            if pregunta is not None:
                for valor in DOMINIOS[pregunta.hecho]:
                    pendientes.append({**respuestas, pregunta.hecho: valor})
                continue

            hojas += 1
            esperado = diagnosticos(respuestas)
            sin_preguntar = [h for h in HECHOS if h not in respuestas]
            combinaciones = 1
            for h in sin_preguntar:
                combinaciones *= len(DOMINIOS[h])
            if combinaciones <= 16:
                completar = itertools.product(*(DOMINIOS[h] for h in sin_preguntar))
            else:
                completar = ([azar.choice(DOMINIOS[h]) for h in sin_preguntar] for _ in range(4))
            for valores in completar:
                verdad = {**respuestas, **dict(zip(sin_preguntar, valores, strict=True))}
                self.assertEqual(esperado, diagnosticos(verdad), verdad)
                comprobaciones += 1
        self.assertGreater(hojas, 10_000)   # la documentación cita esta cifra
        self.assertGreater(comprobaciones, hojas * 3)

    def test_equivale_a_preguntar_todo_con_no_se(self):
        azar = random.Random(42)
        for _ in range(300):
            verdad = {h: azar.choice((*DOMINIOS[h], None)) for h in HECHOS}
            self.assertEqual(diagnosticos(simular(verdad)), diagnosticos(verdad), verdad)


if __name__ == "__main__":
    unittest.main()
