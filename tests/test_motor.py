import copy
import json
import unittest

from sistema_experto.conocimiento import RUTA_POR_DEFECTO, ErrorDeConocimiento, cargar, desde_dict
from sistema_experto.modelo import BaseDeHechos, Regla
from sistema_experto.motor import (
    encadenar_hacia_adelante,
    encadenar_hacia_atras,
    equiparar,
    exportar_red,
    resolver_conflictos,
)

BASE = cargar()


def respuestas(**si_no: bool) -> dict[str, bool]:
    """Todas las preguntas en 'no' salvo las indicadas."""
    r = {hecho: False for hecho in BASE.preguntas}
    r.update(si_no)
    return r


class TestBaseDeConocimiento(unittest.TestCase):
    def test_la_base_incluida_es_valida(self):
        self.assertEqual(len(BASE.reglas), 12)
        self.assertEqual(len(BASE.preguntas), 14)

    def _datos(self):
        with open(RUTA_POR_DEFECTO, encoding="utf-8") as f:
            return json.load(f)

    def _errores(self, datos):
        with self.assertRaises(ErrorDeConocimiento) as ctx:
            desde_dict(datos)
        return "\n".join(ctx.exception.errores)

    def test_detecta_condicion_sin_pregunta_ni_regla(self):
        datos = self._datos()
        datos["reglas"][0]["si"]["sintoma_inventado"] = True
        self.assertIn("sintoma_inventado", self._errores(datos))

    def test_detecta_ids_duplicados(self):
        datos = self._datos()
        datos["reglas"][1]["id"] = datos["reglas"][0]["id"]
        self.assertIn("duplicado", self._errores(datos))

    def test_detecta_condiciones_identicas(self):
        datos = self._datos()
        clon = copy.deepcopy(datos["reglas"][-1])
        clon["id"], clon["entonces"] = "R99", "otra_cosa"
        datos["reglas"].append(clon)
        self.assertIn("mismas condiciones", self._errores(datos))

    def test_detecta_confianza_fuera_de_rango(self):
        datos = self._datos()
        datos["reglas"][0]["confianza"] = 1.5
        self.assertIn("confianza", self._errores(datos))

    def test_detecta_ciclos(self):
        datos = self._datos()
        datos["reglas"].append({
            "id": "X1", "descripcion": "ciclo", "si": {"falla_ram": True, "enciende": True},
            "entonces": "arranque_sin_video", "confianza": 1.0,
        })
        self.assertIn("circular", self._errores(datos))

    def test_detecta_negacion_de_hecho_derivado(self):
        datos = self._datos()
        datos["reglas"][-1]["si"]["rendimiento_degradado"] = False
        self.assertIn("niega el hecho derivado", self._errores(datos))

    def test_detecta_pregunta_sin_uso(self):
        datos = self._datos()
        datos["hechos"]["huerfano"] = {"pregunta": "¿?"}
        self.assertIn("ninguna regla lo usa", self._errores(datos))


class TestEncadenamientoHaciaAdelante(unittest.TestCase):
    def test_sin_sintomas_no_hay_diagnostico(self):
        inferencia = encadenar_hacia_adelante(BASE, respuestas(enciende=True, luces_led=True,
                                                                hay_video=True, conexion_red=True,
                                                                perifericos_responden=True))
        self.assertEqual(inferencia.diagnosticos, [])

    def test_fuente_de_poder(self):
        inferencia = encadenar_hacia_adelante(BASE, respuestas())
        self.assertEqual(inferencia.principal.hecho, "falla_fuente")
        self.assertAlmostEqual(inferencia.principal.certeza, 0.92)

    def test_encadena_hechos_intermedios(self):
        # enciende + sin video → I01 → arranque_sin_video → R02
        inferencia = encadenar_hacia_adelante(
            BASE, respuestas(enciende=True, pitidos_arranque=True, conexion_red=True,
                             perifericos_responden=True))
        ids = [d.regla.id for d in inferencia.disparos]
        self.assertLess(ids.index("I01"), ids.index("R02"))
        self.assertEqual(inferencia.principal.hecho, "falla_ram")
        self.assertEqual([d.regla.id for d in inferencia.justificacion("falla_ram")],
                         ["I01", "R02"])

    def test_negacion_distingue_ram_de_video(self):
        con_pitidos = encadenar_hacia_adelante(BASE, respuestas(enciende=True, pitidos_arranque=True))
        sin_pitidos = encadenar_hacia_adelante(BASE, respuestas(enciende=True))
        hechos_con = {dg.hecho for dg in con_pitidos.diagnosticos}
        hechos_sin = {dg.hecho for dg in sin_pitidos.diagnosticos}
        self.assertIn("falla_ram", hechos_con)
        self.assertNotIn("falla_video", hechos_con)
        self.assertIn("falla_video", hechos_sin)
        self.assertNotIn("falla_ram", hechos_sin)

    def test_ranking_ordenado_por_certeza(self):
        inferencia = encadenar_hacia_adelante(
            BASE, respuestas(enciende=True, hay_video=True, inicia_lento=True, disco_al_100=True,
                             ventilador_siempre_activo=True, conexion_red=True,
                             perifericos_responden=True))
        self.assertEqual([dg.hecho for dg in inferencia.diagnosticos], ["falla_disco", "malware"])

    def test_la_certeza_se_propaga_por_la_cadena(self):
        base = desde_dict({
            "hechos": {"a": {"pregunta": "a?"}, "b": {"pregunta": "b?"}},
            "reglas": [
                {"id": "I", "descripcion": "i", "si": {"a": True}, "entonces": "x", "confianza": 0.5},
                {"id": "D", "descripcion": "d", "si": {"x": True, "b": True}, "entonces": "y",
                 "recomendacion": "r", "confianza": 0.8},
            ],
        })
        inferencia = encadenar_hacia_adelante(base, {"a": True, "b": True})
        self.assertAlmostEqual(inferencia.principal.certeza, 0.4)

    def test_varias_reglas_al_mismo_hecho_combinan_certeza(self):
        base = desde_dict({
            "hechos": {"a": {"pregunta": "a?"}, "b": {"pregunta": "b?"}},
            "reglas": [
                {"id": "D1", "descripcion": "d", "si": {"a": True}, "entonces": "y",
                 "recomendacion": "r1", "confianza": 0.6},
                {"id": "D2", "descripcion": "d", "si": {"b": True}, "entonces": "y",
                 "recomendacion": "r2", "confianza": 0.5},
            ],
        })
        inferencia = encadenar_hacia_adelante(base, {"a": True, "b": True})
        self.assertEqual(len(inferencia.diagnosticos), 1)
        self.assertAlmostEqual(inferencia.principal.certeza, 0.6 + 0.5 * 0.4)

    def test_no_comparte_estado_entre_consultas(self):
        encadenar_hacia_adelante(BASE, respuestas())
        segunda = encadenar_hacia_adelante(BASE, respuestas(enciende=True, luces_led=True,
                                                             hay_video=True, conexion_red=True,
                                                             perifericos_responden=True))
        self.assertIsNone(segunda.principal)

    def test_rechaza_hechos_desconocidos(self):
        with self.assertRaises(ValueError):
            encadenar_hacia_adelante(BASE, {"no_existe": True})

    def test_resolver_conflictos_desempata_por_especificidad(self):
        general = Regla("A", "a", {"x": True}, "p", 0.8)
        especifica = Regla("B", "b", {"x": True, "y": True}, "q", 0.8)
        self.assertIs(resolver_conflictos([general, especifica]), especifica)
        self.assertIsNone(resolver_conflictos([]))

    def test_equiparar_respeta_refraccion(self):
        hechos = BaseDeHechos()
        hechos.afirmar("x")
        regla = Regla("A", "a", {"x": True}, "p", 0.8)
        self.assertEqual(equiparar([regla], hechos), [regla])
        self.assertEqual(equiparar([regla], hechos, {"A"}), [])


class TestEncadenamientoHaciaAtras(unittest.TestCase):
    def test_indica_lo_que_falta(self):
        [analisis] = encadenar_hacia_atras(BASE, "R07", {"enciende": True, "se_apaga_solo": True})
        self.assertFalse(analisis.se_activa)
        self.assertFalse(analisis.descartada)
        self.assertEqual(analisis.por_preguntar, ["calor_excesivo"])

    def test_recorre_hechos_intermedios(self):
        [analisis] = encadenar_hacia_atras(BASE, "R02", {})
        self.assertEqual(analisis.por_preguntar, ["enciende", "hay_video", "pitidos_arranque"])
        intermedia = analisis.condiciones[0]
        self.assertEqual(intermedia.hecho, "arranque_sin_video")
        self.assertEqual(intermedia.subobjetivos[0].regla.id, "I01")

    def test_detecta_contradiccion_en_subobjetivo(self):
        [analisis] = encadenar_hacia_atras(BASE, "R02", {"enciende": True, "hay_video": True})
        self.assertTrue(analisis.descartada)
        self.assertEqual(analisis.por_preguntar, [])

    def test_se_activa(self):
        [analisis] = encadenar_hacia_atras(
            BASE, "falla_ram", {"enciende": True, "hay_video": False, "pitidos_arranque": True})
        self.assertTrue(analisis.se_activa)

    def test_meta_por_descripcion(self):
        [analisis] = encadenar_hacia_atras(BASE, "sobrecalentamiento", {})
        self.assertEqual(analisis.regla.id, "R07")

    def test_meta_inexistente(self):
        with self.assertRaises(LookupError):
            encadenar_hacia_atras(BASE, "R99", {})


class TestExportarRed(unittest.TestCase):
    def test_estructura_del_grafo(self):
        grafo = exportar_red(BASE)
        ids = {n["id"] for n in grafo["nodos"]}
        self.assertEqual(len(ids), len(grafo["nodos"]), "ids de nodo duplicados")
        for arista in grafo["aristas"]:
            self.assertIn(arista["origen"], ids)
            self.assertIn(arista["destino"], ids)
        tipos = {n["id"]: n["tipo"] for n in grafo["nodos"]}
        self.assertEqual(tipos["enciende"], "entrada")
        self.assertEqual(tipos["arranque_sin_video"], "intermedio")
        self.assertEqual(tipos["falla_ram"], "diagnostico")
        self.assertEqual(tipos["R02"], "regla")


if __name__ == "__main__":
    unittest.main()
