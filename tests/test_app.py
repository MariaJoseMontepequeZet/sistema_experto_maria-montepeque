"""
Pruebas de la interfaz web con el simulador oficial de Streamlit.
Se omiten si Streamlit no está instalado (el motor no lo necesita).
"""

import importlib.util
import unittest
from pathlib import Path

HAY_STREAMLIT = importlib.util.find_spec("streamlit") is not None
APP = str(Path(__file__).resolve().parent.parent / "app.py")


@unittest.skipUnless(HAY_STREAMLIT, "Streamlit no está instalado (pip install -r requirements.txt)")
class TestApp(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.app = AppTest.from_file(APP, default_timeout=30).run()

    def clic(self, etiqueta: str) -> None:
        [boton] = [b for b in self.app.button if b.label == etiqueta]
        boton.click().run()
        self.assertFalse(self.app.exception, self.app.exception)

    def clic_no_se(self) -> bool:
        """Responde 'No sé' (o 'No puedo hacerla' en una prueba). False si ya no hay preguntas."""
        for etiqueta in ("No sé", "No puedo hacerla"):
            if any(b.label == etiqueta for b in self.app.button):
                self.clic(etiqueta)
                return True
        return False

    def pregunta(self) -> str:
        return self.app.subheader[0].value

    def test_primera_pregunta(self):
        self.assertFalse(self.app.exception)
        self.assertIn("arranca", self.pregunta())

    def test_consulta_con_pregunta_de_opcion(self):
        self.clic("No")                           # ¿arranca?
        self.assertIn("tipo de equipo", self.pregunta())
        self.clic("Computadora de escritorio")    # pregunta de opción: un botón por opción
        self.clic("No")                           # ¿luces LED?
        self.assertIn("interruptor", self.pregunta())
        self.clic("Sí")                           # el interruptor está encendido
        # pruebas de verificación: otro enchufe no lo arregla; con otra fuente sí
        pruebas = ("Prueba con otra fuente", "Conecta el equipo")
        while self.app.subheader and self.pregunta().startswith(pruebas):
            self.assertIn("No puedo hacerla", [b.label for b in self.app.button])
            self.clic("Sí" if "otra fuente" in self.pregunta() else "No")
        self.assertIn("Fuente de poder dañada", self.app.success[0].value)
        self.assertIn("99%", self.app.success[0].value)
        self.assertIn("Nunca abras la fuente", self.app.warning[0].value)
        self.assertEqual(len(self.app.tabs), 4)

    def test_pregunta_numerica(self):
        self.clic("Sí")                           # ¿arranca?
        # la temperatura solo se pide si hay imagen; el resto se responde "no sé"
        for _ in range(25):
            if self.app.number_input:
                break
            if "imagen" in self.pregunta():
                self.clic("Sí")
            else:
                self.clic_no_se()
        [campo] = self.app.number_input
        self.assertIn("°C", campo.label)
        self.assertTrue([b for b in self.app.button if b.label == "Responder"][0].disabled)
        campo.set_value(95).run()
        self.clic("Responder")
        self.assertNotIn("temperatura", self.pregunta() if self.app.subheader else "")
        self.assertEqual(self.app.session_state["respuestas"]["temperatura_cpu"], 95.0)

    def test_muestra_evidencia_y_descartados(self):
        from sistema_experto import cargar
        base = cargar()
        respuestas = {h: False for h, e in base.hechos.items() if e.tipo == "si_no"}
        respuestas.update(enciende=True, luces_led=True, hay_video=True, perifericos_responden=True,
                          tipo_equipo="escritorio", patron_pitidos="uno_corto", se_apaga_solo=True,
                          calor_excesivo=True, temperatura_cpu=60.0, otras_apps_funcionan=True,
                          otros_dispositivos_conectan=False, hay_sonido=True)
        self.app.session_state["respuestas"] = respuestas
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertIn("router", self.app.success[0].value)
        self.assertIn("🧮 ¿Por qué 75% de certeza?", [e.label for e in self.app.expander])
        self.assertIn("Descartados por evidencia en contra", [s.value for s in self.app.subheader])

    def test_muestra_el_diagnostico_diferencial(self):
        # sobrecalentamiento (90%) y driver o RAM (87%) están cerca
        self.app.session_state["respuestas"] = {
            "enciende": True, "hay_video": True, "se_apaga_solo": True, "calor_excesivo": True,
            "pantalla_azul_frecuente": True}
        self.app.run()
        self.assertFalse(self.app.exception)
        [aviso] = [c.value for c in self.app.caption if "DIAGNÓSTICO DIFERENCIAL" in c.value]
        self.assertIn("Sobrecalentamiento", aviso)

    def test_ver_diagnostico_sin_mas_pruebas(self):
        self.clic("No")
        self.clic("Computadora de escritorio")
        self.clic("No")
        self.clic("Sí")                           # interruptor encendido
        prueba = self.pregunta()
        self.clic("⏭️ Ver el diagnóstico sin más pruebas")
        self.assertIn("Fuente de poder dañada", self.app.success[0].value)
        self.clic("↩️ Deshacer")                  # vuelve a la prueba que se saltó
        self.assertEqual(self.pregunta(), prueba)

    def test_deshacer_vuelve_a_la_pregunta_anterior(self):
        self.clic("No")
        self.assertIn("tipo de equipo", self.pregunta())
        self.clic("↩️ Deshacer")
        self.assertIn("arranca", self.pregunta())

    def test_no_se_no_rompe_la_consulta(self):
        for _ in range(30):   # hay 23 preguntas como máximo
            if not self.clic_no_se():
                break
        self.assertEqual(len(self.app.success), 0)   # sin datos no hay diagnóstico
        self.assertEqual(len(self.app.info), 2)      # avisos en Diagnóstico y Razonamiento


if __name__ == "__main__":
    unittest.main()
