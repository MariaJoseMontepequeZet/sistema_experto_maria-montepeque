import itertools
import os
import random
import unittest

from sistema_experto.conocimiento import cargar
from sistema_experto.modelo import NUMERO, OPCION
from sistema_experto.motor import (
    _Consulta,
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

    def test_no_pide_pruebas_que_ya_no_pueden_cambiar_el_diagnostico(self):
        # El puente confirma el botón y descarta la placa madre (-0.95): aunque "con otra
        # fuente tampoco" sumara 0.7 a la placa, no alcanzaría el umbral. Tampoco sirve ya
        # restarle con la prueba del enchufe.
        r = {"enciende": False, "tipo_equipo": "escritorio", "luces_led": True,
             "interruptor_fuente_encendido": True, "prueba_puente_boton": True}
        self.assertIsNone(siguiente_pregunta(BASE, r))
        self.assertEqual(hipotesis_abiertas(BASE, r), [])
        self.assertEqual(diagnosticos(r), {"falla_boton_encendido"})

    def test_sigue_preguntando_lo_que_todavia_puede_cambiar_el_resultado(self):
        # Sin la prueba del puente, la placa madre todavía puede confirmarse
        r = {"enciende": False, "tipo_equipo": "escritorio", "luces_led": True,
             "interruptor_fuente_encendido": True}
        self.assertEqual(siguiente_pregunta(BASE, r).hecho, "prueba_puente_boton")

    def test_la_cota_de_certeza_nunca_descarta_un_diagnostico_posible(self):
        """
        Solidez de la poda: con cualquier subconjunto de respuestas, todo diagnóstico que
        el equipo completo termine estableciendo debe seguir siendo alcanzable.
        """
        azar = random.Random(7)
        for _ in range(MUESTRAS):
            verdad = {h: azar.choice((*DOMINIOS[h], None)) for h in HECHOS}
            parcial = {h: v for h, v in verdad.items() if azar.random() < 0.5}
            alcanzables = _Consulta(BASE, parcial).alcanzables
            self.assertLessEqual(diagnosticos(verdad), alcanzables, parcial)

    def test_diagnostico_diferencial_pregunta_lo_que_separa(self):
        # Sobrecalentamiento (90%) y driver o RAM (87%) están cerca: el ventilador siempre
        # activo solo aporta evidencia al sobrecalentamiento, así que va antes que el resto.
        r = {"enciende": True, "hay_video": True, "se_apaga_solo": True, "calor_excesivo": True,
             "pantalla_azul_frecuente": True}
        pregunta = siguiente_pregunta(BASE, r)
        self.assertEqual(pregunta.hecho, "ventilador_siempre_activo")
        self.assertEqual({dg.hecho for dg in pregunta.rivales},
                         {"sobrecalentamiento", "falla_driver_o_ram"})

        # Con un solo diagnóstico no hay nada que separar: se sigue el orden habitual
        del r["pantalla_azul_frecuente"]
        pregunta = siguiente_pregunta(BASE, r)
        self.assertEqual(pregunta.rivales, ())
        self.assertNotEqual(pregunta.hecho, "ventilador_siempre_activo")

    def test_diferencial_entre_varios_diagnosticos_cercanos(self):
        # Audio (90%), router y disco (85%) y malware (72%) compiten: la prueba del antivirus
        # es la que más puede cambiar el orden (el malware subiría al 97% o bajaría al 44%).
        r = {"enciende": True, "hay_video": True, "inicia_lento": True, "disco_al_100": True,
             "ventilador_siempre_activo": True, "hay_sonido": False, "salida_audio_correcta": False,
             "conexion_red": False, "otros_dispositivos_conectan": False, "se_apaga_solo": False,
             "pantalla_azul_frecuente": False, "fecha_hora_incorrecta": False,
             "patron_pitidos": "ninguno", "perifericos_responden": True, "tipo_equipo": "escritorio"}
        pregunta = siguiente_pregunta(BASE, r)
        self.assertEqual(pregunta.hecho, "prueba_antivirus")
        self.assertEqual({dg.hecho for dg in pregunta.rivales}, {"audio_mal_configurado", "malware"})

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
