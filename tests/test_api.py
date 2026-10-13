"""
Pruebas de la API REST con el cliente de pruebas de FastAPI.
Se omiten si FastAPI no está instalado (el motor no lo necesita).
"""

import importlib.util
import os
import unittest
from unittest import mock

HAY_FASTAPI = (importlib.util.find_spec("fastapi") is not None
               and importlib.util.find_spec("httpx") is not None)


@unittest.skipUnless(HAY_FASTAPI, "FastAPI no está instalado (pip install -r requirements-api.txt)")
class TestApi(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from sistema_experto.api import app
        self.cliente = TestClient(app)

    def siguiente(self, respuestas, **extra):
        return self.cliente.post("/v1/consulta/siguiente", json={"respuestas": respuestas, **extra})

    def resultado(self, respuestas):
        return self.cliente.post("/v1/consulta/resultado", json={"respuestas": respuestas})

    def test_salud(self):
        self.assertEqual(self.cliente.get("/salud").json()["estado"], "ok")

    def test_conocimiento_lista_las_preguntas(self):
        datos = self.cliente.get("/v1/conocimiento").json()
        self.assertEqual(datos["diagnosticos"], 21)
        tipos = {p["tipo"] for p in datos["preguntas"]}
        self.assertEqual(tipos, {"si_no", "opcion", "numero"})

    def test_primera_pregunta(self):
        datos = self.siguiente({}).json()
        self.assertFalse(datos["terminada"])
        self.assertEqual(datos["pregunta"]["hecho"], "enciende")
        self.assertEqual(datos["progreso"]["respondidas"], 0)
        progreso = datos["progreso"]   # abiertas = fallas distintas: nunca más que las posibles
        self.assertEqual(progreso["hipotesis_abiertas"], progreso["diagnosticos_posibles"])

    def test_pregunta_de_opcion_incluye_opciones(self):
        pregunta = self.siguiente({"enciende": False}).json()["pregunta"]
        self.assertEqual(pregunta["hecho"], "tipo_equipo")
        self.assertEqual([o["valor"] for o in pregunta["opciones"]], ["escritorio", "laptop"])

    def test_consulta_completa_hasta_el_diagnostico(self):
        respuestas = {}
        for _ in range(40):
            datos = self.siguiente(respuestas).json()
            if datos["terminada"]:
                break
            pregunta = datos["pregunta"]
            if pregunta["tipo"] == "opcion":
                respuestas[pregunta["hecho"]] = pregunta["opciones"][0]["valor"]
            elif pregunta["tipo"] == "numero":
                respuestas[pregunta["hecho"]] = pregunta["minimo"]
            else:
                respuestas[pregunta["hecho"]] = None   # "no sé" siempre vale
        else:
            self.fail("La consulta no terminó")
        self.assertEqual(self.resultado(respuestas).status_code, 200)

    def test_resultado_con_razonamiento(self):
        datos = self.resultado({"enciende": False, "tipo_equipo": "escritorio", "luces_led": False,
                                "interruptor_fuente_encendido": True}).json()
        principal = datos["diagnosticos"][0]
        self.assertGreater(principal["certeza"], 0.2)
        self.assertTrue(principal["recomendaciones"])
        self.assertTrue(principal["razonamiento"])
        self.assertIn("orienta", datos["aviso"])

    def test_hecho_desconocido_se_rechaza(self):
        r = self.siguiente({"inventado": True})
        self.assertEqual(r.status_code, 422)
        self.assertIn("inventado", r.json()["detail"][0])

    def test_respuesta_invalida_se_rechaza(self):
        self.assertEqual(self.siguiente({"tipo_equipo": "tablet"}).status_code, 422)
        self.assertEqual(self.siguiente({"enciende": "si"}).status_code, 422)

    def test_omitir_pruebas_termina(self):
        self.assertTrue(self.siguiente({}, omitir_pruebas=True).json()["terminada"])

    def test_precision(self):
        datos = self.cliente.get("/v1/precision").json()
        self.assertGreaterEqual(datos["precision"], 0.9)

    def test_sin_claves_configuradas_la_api_esta_abierta(self):
        with mock.patch.dict(os.environ, {"SISTEMA_EXPERTO_API_KEYS": ""}):
            self.assertEqual(self.cliente.get("/v1/conocimiento").status_code, 200)

    def test_con_claves_configuradas_se_exige_una_valida(self):
        with mock.patch.dict(os.environ, {"SISTEMA_EXPERTO_API_KEYS": "clave-a, clave-b"}):
            self.assertEqual(self.cliente.get("/v1/conocimiento").status_code, 401)
            malas = self.cliente.get("/v1/conocimiento", headers={"X-API-Key": "otra"})
            self.assertEqual(malas.status_code, 401)
            buena = self.cliente.get("/v1/conocimiento", headers={"X-API-Key": "clave-b"})
            self.assertEqual(buena.status_code, 200)
            self.assertEqual(self.cliente.get("/salud").status_code, 200)   # la salud nunca pide clave


if __name__ == "__main__":
    unittest.main()
