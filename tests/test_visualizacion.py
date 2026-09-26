import unittest

from sistema_experto.conocimiento import cargar
from sistema_experto.motor import encadenar_hacia_adelante
from sistema_experto.visualizacion import _texto, dot_razonamiento, dot_red

BASE = cargar()


class TestVisualizacion(unittest.TestCase):
    def test_red_completa(self):
        dot = dot_red(BASE)
        self.assertTrue(dot.startswith("digraph G {") and dot.endswith("}"))
        for regla in BASE.reglas:
            self.assertIn(f'"regla:{regla.id}"', dot)
        # R01 niega 'enciende': la arista debe ir punteada
        self.assertIn('"enciende" -> "regla:R01" [style=dashed, label="no"];', dot)
        self.assertIn('"regla:I01" -> "arranque_sin_video";', dot)

    def test_red_muestra_opciones_y_rangos(self):
        dot = dot_red(BASE)
        self.assertIn('"tipo_equipo" -> "regla:R11" [label="Laptop"];', dot)
        self.assertIn('"temperatura_cpu" -> "regla:R14" [label="≥ 90 °C"];', dot)

    def test_razonamiento_solo_incluye_la_cadena(self):
        inferencia = encadenar_hacia_adelante(BASE, {
            "enciende": True, "hay_video": False, "patron_pitidos": "repetidos",
            "fecha_hora_incorrecta": True,
        })
        dot = dot_razonamiento(inferencia, "falla_ram", BASE)
        self.assertIn('"regla:I01"', dot)
        self.assertIn('"regla:R02"', dot)
        self.assertNotIn('"regla:R08"', dot)            # otro diagnóstico, no es parte de la cadena
        self.assertIn('label="hay_video = no"', dot)
        self.assertIn('label="patron_pitidos = Pitidos repetidos o continuos"', dot)
        self.assertIn('"arranque_sin_video" -> "regla:R02";', dot)

    def test_razonamiento_con_respuesta_numerica(self):
        inferencia = encadenar_hacia_adelante(BASE, {"enciende": True, "temperatura_cpu": 95.0})
        dot = dot_razonamiento(inferencia, "sobrecalentamiento", BASE)
        self.assertIn('label="temperatura_cpu = 95 °C"', dot)

    def test_escapa_comillas_y_saltos(self):
        self.assertEqual(_texto('a "b"\nc'), '"a \\"b\\"\\nc"')


if __name__ == "__main__":
    unittest.main()
