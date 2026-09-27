import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from sistema_experto.cli import main
from sistema_experto.conocimiento import ErrorDeConocimiento, cargar
from sistema_experto.validacion import (
    PRECISION_MINIMA,
    Caso,
    Evaluacion,
    ResultadoCaso,
    cargar_casos,
    evaluar,
    informe,
    simular_consulta,
)

BASE = cargar()
CASOS = cargar_casos(BASE)
EVALUACION = evaluar(BASE, CASOS)


class TestCasosDeReferencia(unittest.TestCase):
    def test_los_casos_son_validos_y_cubren_cada_diagnostico(self):
        esperados = {c.esperado for c in CASOS}
        self.assertTrue(BASE.hechos_diagnostico <= esperados,
                        f"diagnósticos sin caso: {sorted(BASE.hechos_diagnostico - esperados)}")
        self.assertIn(None, esperados, "debe haber casos de control sin falla")

    def test_precision_minima(self):
        self.assertGreaterEqual(EVALUACION.precision, PRECISION_MINIMA, "\n" + informe(EVALUACION))

    def test_no_inventa_fallas(self):
        self.assertEqual(EVALUACION.falsos_positivos, [], "\n" + informe(EVALUACION))

    def test_los_casos_fuera_de_cobertura_se_reportan_aparte(self):
        fuera = {r.caso.id for r in EVALUACION.fuera_de_cobertura}
        self.assertIn("C29", fuera)
        self.assertNotIn("C29", {r.caso.id for r in EVALUACION.fallos})

    def test_la_consulta_simulada_no_pregunta_de_mas(self):
        # C01: escritorio sin señales de vida → 3 síntomas y 1 prueba de verificación
        [c01] = [r for r in EVALUACION.resultados if r.caso.id == "C01"]
        self.assertEqual(c01.preguntas, 4)

    def test_lo_que_el_caso_no_indica_se_responde_no_se(self):
        respuestas = simular_consulta(BASE, {"enciende": False, "tipo_equipo": "escritorio"})
        self.assertIsNone(respuestas["luces_led"])


class TestMetricas(unittest.TestCase):
    def resultado(self, esperado, ranking, certeza=0.9, cubierto=True):
        caso = Caso(id="X", descripcion="x", respuestas={}, esperado=esperado)
        return ResultadoCaso(caso, tuple(ranking), certeza if ranking else None, 5, cubierto)

    def test_precision_top3_falsos_positivos_y_calibracion(self):
        evaluacion = Evaluacion((
            self.resultado("a", ["a"], 0.95),
            self.resultado("a", ["b", "a"], 0.85),        # falla, pero está entre los 3 primeros
            self.resultado(None, ["c"], 0.6),             # falso positivo
            self.resultado(None, []),                     # control correcto
            self.resultado("z", [], cubierto=False),      # fuera de cobertura: no cuenta
        ))
        self.assertAlmostEqual(evaluacion.precision, 2 / 4)
        self.assertAlmostEqual(evaluacion.precision_top3, 3 / 4)
        self.assertEqual(len(evaluacion.falsos_positivos), 1)
        calibracion = {rango: (n, aciertos) for rango, n, aciertos in evaluacion.calibracion()}
        self.assertEqual(calibracion["90–100 %"], (1, 1.0))
        self.assertEqual(calibracion["80–90 %"], (1, 0.0))
        self.assertEqual(calibracion["50–80 %"], (1, 0.0))


class TestFormatoDeCasos(unittest.TestCase):
    def errores(self, datos: dict) -> str:
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "casos.json"
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            with self.assertRaises(ErrorDeConocimiento) as ctx:
                cargar_casos(BASE, ruta)
        return "\n".join(ctx.exception.errores)

    def test_detecta_errores_de_formato(self):
        casos = [
            {"id": "A", "respuestas": {"no_existe": True}, "esperado": None},
            {"id": "B", "respuestas": {"tipo_equipo": "tablet"}, "esperado": None},
            {"id": "C", "plantilla": "inexistente", "esperado": None},
            {"id": "D", "respuestas": {}},
            {"id": "D", "respuestas": {}, "esperado": None},
        ]
        errores = self.errores({"casos": casos})
        self.assertIn("'no_existe' no es una pregunta", errores)
        self.assertIn("'tablet' no es una respuesta válida", errores)
        self.assertIn("la plantilla 'inexistente' no existe", errores)
        self.assertIn("falta 'esperado'", errores)
        self.assertIn("ID duplicado", errores)


def ejecutar(*argumentos: str) -> tuple[int, str]:
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        codigo = main(list(argumentos))
    return codigo, salida.getvalue()


class TestLineaDeComandos(unittest.TestCase):
    def test_validar_devuelve_0_si_cumple_el_minimo(self):
        codigo, salida = ejecutar("--validar")
        self.assertEqual(codigo, 0)
        self.assertIn("Precisión (diagnóstico principal correcto)", salida)

    def test_validar_devuelve_1_si_no_cumple(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "casos.json"
            # un caso imposible de acertar: equipo sano del que se espera una falla de RAM
            ruta.write_text(json.dumps({"casos": [{"id": "X", "respuestas": {}, "esperado": "falla_ram"}]}),
                            encoding="utf-8")
            codigo, salida = ejecutar("--validar", "--casos", str(ruta))
            self.assertEqual(codigo, 1)
            self.assertIn("por debajo del mínimo", salida)


if __name__ == "__main__":
    unittest.main()
