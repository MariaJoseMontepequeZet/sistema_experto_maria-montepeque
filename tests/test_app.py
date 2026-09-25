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

    def test_primera_pregunta(self):
        self.assertFalse(self.app.exception)
        self.assertIn("arranca", self.app.subheader[0].value)

    def test_consulta_completa_hasta_el_diagnostico(self):
        self.clic("No")   # ¿arranca?
        self.clic("No")   # ¿luces LED?
        self.assertIn("Fuente de poder dañada", self.app.success[0].value)
        self.assertIn("Nunca abras la fuente", self.app.warning[0].value)
        self.assertEqual(len(self.app.tabs), 4)

    def test_deshacer_vuelve_a_la_pregunta_anterior(self):
        self.clic("No")
        self.assertIn("LED", self.app.subheader[0].value)
        self.clic("↩️ Deshacer")
        self.assertIn("arranca", self.app.subheader[0].value)

    def test_no_se_no_rompe_la_consulta(self):
        for _ in range(20):   # hay 14 preguntas como máximo
            if not [b for b in self.app.button if b.label == "No sé"]:
                break
            self.clic("No sé")
        self.assertEqual(len(self.app.success), 0)   # sin datos no hay diagnóstico
        self.assertEqual(len(self.app.info), 2)      # avisos en Diagnóstico y Razonamiento


if __name__ == "__main__":
    unittest.main()
