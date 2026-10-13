"""
Pruebas del informe PDF y de su ruta en la API. Se omiten si falta reportlab o FastAPI.
"""

import base64
import importlib.util
import unittest

HAY_REPORTLAB = importlib.util.find_spec("reportlab") is not None
HAY_API = (HAY_REPORTLAB and importlib.util.find_spec("fastapi") is not None
           and importlib.util.find_spec("httpx") is not None)

FUENTE = {"enciende": False, "tipo_equipo": "escritorio", "luces_led": False,
          "interruptor_fuente_encendido": True}


def png_minimo() -> bytes:
    """Un PNG válido de 1x1, sin depender de Pillow."""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


@unittest.skipUnless(HAY_REPORTLAB, "reportlab no está instalado (pip install -r requirements-api.txt)")
class TestInforme(unittest.TestCase):
    def setUp(self):
        from sistema_experto.conocimiento import cargar
        from sistema_experto.motor import encadenar_hacia_adelante
        self.base = cargar()
        self.inferir = lambda r: encadenar_hacia_adelante(self.base, r)

    def pdf(self, respuestas, **kwargs):
        from sistema_experto.informe import generar_pdf
        return generar_pdf(self.base, respuestas, self.inferir(respuestas), comprimir=False, **kwargs)

    def test_es_un_pdf_con_el_diagnostico(self):
        pdf = self.pdf(FUENTE)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"Fuente de poder da", pdf)
        self.assertIn(b"Nunca abras la fuente", pdf)

    def test_incluye_marca_y_datos_del_servicio(self):
        from sistema_experto.informe import DatosServicio, Marca
        pdf = self.pdf(FUENTE, marca=Marca("Taller Los Pinos", "#0b6e4f", "Tel. 5555-1234"),
                       servicio=DatosServicio(cliente="Ana", equipo="Laptop HP", tecnico="Carlos"))
        for esperado in (b"Taller Los Pinos", b"Tel. 5555-1234", b"Ana", b"Laptop HP", b"Carlos"):
            self.assertIn(esperado, pdf)

    def test_el_texto_del_usuario_no_se_interpreta_como_marcado(self):
        from sistema_experto.informe import DatosServicio
        pdf = self.pdf(FUENTE, servicio=DatosServicio(cliente="<b>Ana</b> & Co"))
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"(> & Co)", pdf)       # el marcado se dibuja como texto literal

    def test_sin_diagnostico_lo_dice(self):
        self.assertIn(b"suficiente certeza", self.pdf({}))

    def test_logo_valido_e_invalido(self):
        from sistema_experto.informe import Marca
        self.assertTrue(self.pdf(FUENTE, marca=Marca(logo=png_minimo())).startswith(b"%PDF"))
        with self.assertRaises((ValueError, OSError)):
            Marca(logo=b"esto no es una imagen")

    def test_color_invalido(self):
        from sistema_experto.informe import Marca
        with self.assertRaises(ValueError):
            Marca(color="rojo-clarito")

    def test_cualquier_caso_de_referencia_genera_un_pdf(self):
        from sistema_experto.validacion import cargar_casos
        for caso in cargar_casos(self.base):
            self.assertTrue(self.pdf(caso.respuestas).startswith(b"%PDF"), caso)


@unittest.skipUnless(HAY_API, "FastAPI o reportlab no están instalados (pip install -r requirements-api.txt)")
class TestRutaInforme(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from sistema_experto.api import app
        self.cliente = TestClient(app)

    def informe(self, **extra):
        return self.cliente.post("/v1/consulta/informe", json={"respuestas": FUENTE, **extra})

    def test_devuelve_un_pdf_descargable(self):
        r = self.informe(marca={"nombre": "Taller Los Pinos", "color": "#0b6e4f"},
                         servicio={"cliente": "Ana", "equipo": "Laptop HP"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "application/pdf")
        self.assertIn("attachment", r.headers["content-disposition"])
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_con_logo(self):
        logo = base64.b64encode(png_minimo()).decode()
        self.assertEqual(self.informe(marca={"logo_base64": logo}).status_code, 200)

    def test_logo_invalido_se_rechaza(self):
        self.assertEqual(self.informe(marca={"logo_base64": "no-es-base64!!"}).status_code, 422)
        basura = base64.b64encode(b"no es una imagen").decode()
        self.assertEqual(self.informe(marca={"logo_base64": basura}).status_code, 422)

    def test_color_invalido_se_rechaza(self):
        self.assertEqual(self.informe(marca={"color": "azul"}).status_code, 422)

    def test_respuestas_invalidas_se_rechazan(self):
        r = self.cliente.post("/v1/consulta/informe", json={"respuestas": {"inventado": True}})
        self.assertEqual(r.status_code, 422)

    def test_exige_clave_si_esta_configurada(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"SISTEMA_EXPERTO_API_KEYS": "clave"}):
            self.assertEqual(self.informe().status_code, 401)


if __name__ == "__main__":
    unittest.main()
