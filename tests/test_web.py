"""
Pruebas de que la API sirve la interfaz web (web/public). Se omiten si falta FastAPI.
El JS compilado se versiona: si estas pruebas fallan, ejecuta `npm run build` en web/.
"""

import importlib.util
import unittest
from pathlib import Path

HAY_API = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None
PUBLICO = Path(__file__).resolve().parent.parent / "web" / "public"
FUENTES = Path(__file__).resolve().parent.parent / "web" / "src"


@unittest.skipUnless(HAY_API, "FastAPI no está instalado (pip install -r requirements-api.txt)")
class TestWeb(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from sistema_experto.api import app
        self.web = TestClient(app)

    def test_la_raiz_lleva_a_la_aplicacion(self):
        r = self.web.get("/", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (307, "/app/"))

    def test_sirve_la_pagina_y_sus_recursos(self):
        pagina = self.web.get("/app/")
        self.assertEqual(pagina.status_code, 200)
        self.assertIn("text/html", pagina.headers["content-type"])
        self.assertIn('src="js/main.js"', pagina.text)
        self.assertEqual(self.web.get("/app/css/estilo.css").status_code, 200)
        js = self.web.get("/app/js/main.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn("javascript", js.headers["content-type"])

    def test_la_interfaz_no_abre_la_api_a_nadie(self):
        """Servir la página no debe dejar pasar llamadas sin clave cuando hay claves configuradas."""
        import os
        from unittest import mock
        abierto = {"SISTEMA_EXPERTO_API_KEYS": "clave", "SISTEMA_EXPERTO_ADMIN_KEY": ""}
        with mock.patch.dict(os.environ, abierto):
            self.assertEqual(self.web.get("/app/").status_code, 200)
            self.assertEqual(self.web.get("/v1/conocimiento").status_code, 401)

    def test_el_js_compilado_esta_al_dia_con_las_fuentes(self):
        """Cada módulo de src/ tiene su .js compilado (si falta alguno, falta correr `npm run build`)."""
        for fuente in FUENTES.glob("*.ts"):
            self.assertTrue((PUBLICO / "js" / f"{fuente.stem}.js").is_file(), fuente.name)


if __name__ == "__main__":
    unittest.main()
