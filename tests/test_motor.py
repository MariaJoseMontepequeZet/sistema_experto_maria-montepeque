import copy
import json
import random
import unittest

from sistema_experto.conocimiento import RUTA_POR_DEFECTO, ErrorDeConocimiento, cargar, desde_dict
from sistema_experto.modelo import (
    NUMERO,
    OPCION,
    SI_NO,
    UMBRAL_CERTEZA,
    BaseDeConocimiento,
    BaseDeHechos,
    Condicion,
    Hecho,
    Regla,
    combinar_certezas,
)
from sistema_experto.motor import (
    encadenar_hacia_adelante,
    encadenar_hacia_atras,
    equiparar,
    exportar_red,
    pregunta_sobre,
    resolver_conflictos,
)

BASE = cargar()


def respuestas(**valores) -> dict:
    """Consulta de referencia: síntomas en 'no', escritorio, sin pitidos, y las pruebas de
    verificación sin hacer (desconocidas), salvo lo indicado."""
    r = {hecho: (None if h.prueba else False) for hecho, h in BASE.hechos.items() if h.tipo == SI_NO}
    r.update(tipo_equipo="escritorio", patron_pitidos="ninguno", temperatura_cpu=None)
    r.update(valores)
    return r


def equipo_sano(**valores) -> dict:
    """Equipo que enciende y funciona bien; se agregan solo los síntomas del caso."""
    return respuestas(**{"enciende": True, "luces_led": True, "hay_video": True, "conexion_red": True,
                         "perifericos_responden": True, "otras_apps_funcionan": True,
                         "otros_dispositivos_conectan": True, **valores})


def diagnosticos(r: dict) -> dict[str, float]:
    return {dg.hecho: round(dg.certeza, 4) for dg in encadenar_hacia_adelante(BASE, r).diagnosticos}


class TestBaseDeConocimiento(unittest.TestCase):
    def test_la_base_incluida_es_valida(self):
        self.assertEqual(len(BASE.reglas), 36)
        self.assertEqual(len(BASE.hechos), 23)
        self.assertEqual(sum(h.prueba for h in BASE.hechos.values()), 7)
        self.assertEqual({h.tipo for h in BASE.hechos.values()}, {SI_NO, OPCION, NUMERO})

    def _datos(self):
        with open(RUTA_POR_DEFECTO, encoding="utf-8") as f:
            return json.load(f)

    def _errores(self, datos):
        with self.assertRaises(ErrorDeConocimiento) as ctx:
            desde_dict(datos)
        return "\n".join(ctx.exception.errores)

    def _regla(self, datos, id_regla):
        return next(r for r in datos["reglas"] if r["id"] == id_regla)

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
        clon = copy.deepcopy(self._regla(datos, "R10"))
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

    def test_detecta_campos_desconocidos(self):
        datos = self._datos()
        datos["reglas"][0]["advertancia"] = "typo"
        self.assertIn("campos desconocidos ['advertancia']", self._errores(datos))

    def test_advertencia_requiere_recomendacion(self):
        datos = self._datos()
        regla_intermedia = next(r for r in datos["reglas"] if "recomendacion" not in r)
        regla_intermedia["advertencia"] = "cuidado"
        self.assertIn("solo tiene sentido junto a una 'recomendacion'", self._errores(datos))

    def test_detecta_pregunta_sin_uso(self):
        datos = self._datos()
        datos["hechos"]["huerfano"] = {"pregunta": "¿?"}
        self.assertIn("ninguna regla lo usa", self._errores(datos))

    # ── Tipos de pregunta ──────────────────────────────────────

    def test_detecta_tipo_desconocido(self):
        datos = self._datos()
        datos["hechos"]["enciende"]["tipo"] = "texto"
        self.assertIn("'tipo' debe ser uno de", self._errores(datos))

    def test_opcion_requiere_al_menos_dos_opciones(self):
        datos = self._datos()
        datos["hechos"]["tipo_equipo"]["opciones"] = {"laptop": "Laptop"}
        self.assertIn("al menos 2 opciones", self._errores(datos))

    def test_detecta_opcion_inexistente_en_una_regla(self):
        datos = self._datos()
        self._regla(datos, "R11")["si"]["tipo_equipo"] = "tablet"
        self.assertIn("no tiene las opciones ['tablet']", self._errores(datos))

    def test_detecta_condicion_de_otro_tipo(self):
        datos = self._datos()
        self._regla(datos, "R11")["si"]["tipo_equipo"] = True
        self.assertIn("no corresponde a un hecho de tipo 'opcion'", self._errores(datos))

    def test_detecta_rango_imposible(self):
        datos = self._datos()
        self._regla(datos, "R14")["si"]["temperatura_cpu"] = {">": 90, "<": 80}
        self.assertIn("nunca se puede cumplir", self._errores(datos))

    def test_detecta_operador_desconocido(self):
        datos = self._datos()
        self._regla(datos, "R14")["si"]["temperatura_cpu"] = {"=>": 90}
        self.assertIn("operadores desconocidos ['=>']", self._errores(datos))

    def test_detecta_campos_que_no_corresponden_al_tipo(self):
        datos = self._datos()
        datos["hechos"]["enciende"]["unidad"] = "°C"
        self.assertIn("campos no válidos para el tipo 'si_no' ['unidad']", self._errores(datos))

    def test_minimo_debe_ser_menor_que_maximo(self):
        datos = self._datos()
        datos["hechos"]["temperatura_cpu"]["minimo"] = 200
        self.assertIn("'minimo' debe ser menor que 'maximo'", self._errores(datos))


class TestCondicion(unittest.TestCase):
    def test_si_no_no_confunde_numeros_con_booleanos(self):
        self.assertTrue(Condicion.desde(True).cumple(True))
        self.assertFalse(Condicion.desde(True).cumple(1.0))       # 1.0 == True en Python
        self.assertFalse(Condicion.desde({">=": 1}).cumple(True))  # un sí/no no es un número

    def test_opcion_unica_y_lista(self):
        unica, lista = Condicion.desde("laptop"), Condicion.desde(["a", "b"])
        self.assertTrue(unica.cumple("laptop"))
        self.assertFalse(unica.cumple("escritorio"))
        self.assertTrue(lista.cumple("b"))
        self.assertFalse(lista.cumple(None))

    def test_rango_numerico_con_limites(self):
        rango = Condicion.desde({">=": 80, "<": 90})
        self.assertTrue(rango.cumple(80))
        self.assertTrue(rango.cumple(89.9))
        self.assertFalse(rango.cumple(90))
        self.assertFalse(rango.cumple(79.9))

    def test_describir(self):
        temperatura, pitidos = BASE.hechos["temperatura_cpu"], BASE.hechos["patron_pitidos"]
        self.assertEqual(Condicion.desde({">=": 90}).describir(temperatura), "≥ 90 °C")
        self.assertEqual(Condicion.desde(["ninguno", "uno_corto"]).describir(pitidos),
                         "Ningún pitido o Un solo pitido corto")
        self.assertEqual(Condicion.desde(False).describir(), "no")

    def test_formato_invalido(self):
        for spec in ([], "", {}, {">": "noventa"}, 3):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                Condicion.desde(spec)

    def test_hecho_admite_segun_tipo(self):
        temperatura = BASE.hechos["temperatura_cpu"]
        self.assertTrue(temperatura.admite(55.5))
        self.assertTrue(temperatura.admite(None))          # "no sé"
        self.assertFalse(temperatura.admite(200))          # fuera de rango
        self.assertFalse(temperatura.admite(True))
        self.assertFalse(BASE.hechos["tipo_equipo"].admite("tablet"))
        self.assertFalse(Hecho("x", "¿x?").admite("sí"))


class TestEncadenamientoHaciaAdelante(unittest.TestCase):
    def test_sin_sintomas_no_hay_diagnostico(self):
        self.assertEqual(diagnosticos(equipo_sano()), {})

    def test_fuente_de_poder(self):
        inferencia = encadenar_hacia_adelante(BASE, respuestas())
        self.assertEqual(inferencia.principal.hecho, "falla_fuente")
        self.assertAlmostEqual(inferencia.principal.certeza, 0.92)
        [advertencia] = inferencia.principal.advertencias
        self.assertIn("Nunca abras la fuente", advertencia)

    def test_tipo_de_equipo_distingue_fuente_de_cargador(self):
        self.assertEqual(diagnosticos(respuestas(tipo_equipo="laptop")), {"falla_alimentacion_laptop": 0.85})
        self.assertEqual(diagnosticos(respuestas(tipo_equipo=None)), {})   # sin saberlo, no se adivina

    def test_diagnosticos_que_abren_el_equipo_tienen_advertencia(self):
        abre_equipo = ("falla_fuente", "falla_ram", "falla_video", "sobrecalentamiento",
                       "pila_bios_agotada", "falla_alimentacion_laptop")
        for regla in BASE.reglas:
            if regla.conclusion in abre_equipo and regla.es_diagnostico:
                self.assertTrue(regla.advertencia, f"{regla.id} no tiene advertencia")

    def test_encadena_hechos_intermedios(self):
        # enciende + sin video → I01 → arranque_sin_video → R02
        inferencia = encadenar_hacia_adelante(
            BASE, equipo_sano(hay_video=False, patron_pitidos="repetidos"))
        ids = [d.regla.id for d in inferencia.disparos]
        self.assertLess(ids.index("I01"), ids.index("R02"))
        self.assertEqual(inferencia.principal.hecho, "falla_ram")
        self.assertEqual([d.regla.id for d in inferencia.justificacion("falla_ram")], ["I01", "R02"])

    def test_patron_de_pitidos_distingue_la_causa_sin_imagen(self):
        casos = {
            "repetidos": {"falla_ram": 0.88},
            "largo_y_cortos": {"falla_video": 0.9},
            "ninguno": {"falla_video": 0.7},
            "uno_corto": {"falla_monitor": 0.8},   # arranque normal: no es la RAM
            "otro": {},
        }
        for patron, esperado in casos.items():
            with self.subTest(patron=patron):
                self.assertEqual(diagnosticos(equipo_sano(hay_video=False, patron_pitidos=patron)), esperado)

    def test_condicion_con_lista_de_opciones(self):
        for patron, detecta_usb in (("ninguno", True), ("uno_corto", True), ("repetidos", False)):
            with self.subTest(patron=patron):
                r = equipo_sano(perifericos_responden=False, patron_pitidos=patron)
                self.assertEqual("falla_usb" in diagnosticos(r), detecta_usb)

    def test_pila_bios_ya_no_exige_pitidos(self):
        self.assertEqual(diagnosticos(equipo_sano(fecha_hora_incorrecta=True)), {"pila_bios_agotada": 0.85})

    def test_umbral_de_temperatura(self):
        self.assertEqual(diagnosticos(equipo_sano(temperatura_cpu=90)), {"sobrecalentamiento": 0.9})
        self.assertEqual(diagnosticos(equipo_sano(temperatura_cpu=89.9)), {})

    def test_se_apaga_solo_con_temperatura_normal_apunta_a_la_fuente(self):
        self.assertEqual(diagnosticos(equipo_sano(se_apaga_solo=True, temperatura_cpu=79)),
                         {"falla_fuente": 0.65})
        self.assertEqual(diagnosticos(equipo_sano(se_apaga_solo=True, temperatura_cpu=80)), {})
        self.assertEqual(diagnosticos(equipo_sano(se_apaga_solo=True, temperatura_cpu=79,
                                                  tipo_equipo="laptop")), {})

    def test_evidencias_independientes_se_combinan(self):
        # R07 (chasis caliente) + R14 (temperatura medida) → 0.9 + 0.9 × 0.1
        r = equipo_sano(se_apaga_solo=True, calor_excesivo=True, temperatura_cpu=95)
        self.assertEqual(diagnosticos(r), {"sobrecalentamiento": 0.99})

    def test_ranking_ordenado_por_certeza(self):
        inferencia = encadenar_hacia_adelante(
            BASE, equipo_sano(inicia_lento=True, disco_al_100=True, ventilador_siempre_activo=True))
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
        self.assertIsNone(encadenar_hacia_adelante(BASE, equipo_sano()).principal)

    def test_rechaza_hechos_desconocidos(self):
        with self.assertRaises(ValueError):
            encadenar_hacia_adelante(BASE, {"no_existe": True})

    def test_rechaza_respuestas_que_no_corresponden_al_tipo(self):
        for hecho, valor in (("tipo_equipo", "tablet"), ("temperatura_cpu", 200),
                             ("temperatura_cpu", True), ("enciende", "si")):
            with self.subTest(hecho=hecho, valor=valor), self.assertRaises(ValueError):
                encadenar_hacia_adelante(BASE, {hecho: valor})

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


def base_de_prueba(*reglas: dict, hechos: str = "abc") -> BaseDeConocimiento:
    return desde_dict({"hechos": {h: {"pregunta": f"{h}?"} for h in hechos}, "reglas": list(reglas)})


class TestEvidencia(unittest.TestCase):
    def test_combinacion_mycin(self):
        self.assertAlmostEqual(combinar_certezas(0.6, 0.5), 0.8)       # ambas a favor
        self.assertAlmostEqual(combinar_certezas(-0.5, -0.5), -0.75)   # ambas en contra
        self.assertAlmostEqual(combinar_certezas(0.9, -0.6), 0.75)     # signos opuestos
        self.assertAlmostEqual(combinar_certezas(1, -1), 0.0)          # contradicción total

    def test_combinacion_es_conmutativa_y_acotada(self):
        azar = random.Random(7)
        for _ in range(1000):
            a, b = azar.uniform(-1, 1), azar.uniform(-1, 1)
            self.assertAlmostEqual(combinar_certezas(a, b), combinar_certezas(b, a))
            self.assertLessEqual(abs(combinar_certezas(a, b)), 1)

    def test_evidencia_en_contra_baja_la_certeza(self):
        # R07 (chasis caliente, 0.9) y E01 (procesador a 60 °C, -0.6) → 0.75
        inferencia = encadenar_hacia_adelante(
            BASE, equipo_sano(se_apaga_solo=True, calor_excesivo=True, temperatura_cpu=60))
        [sobrecalentamiento] = [dg for dg in inferencia.diagnosticos if dg.hecho == "sobrecalentamiento"]
        self.assertAlmostEqual(sobrecalentamiento.certeza, 0.75)
        self.assertEqual([d.regla.id for d in sobrecalentamiento.a_favor], ["R07"])
        self.assertEqual([d.regla.id for d in sobrecalentamiento.en_contra], ["E01"])
        # y aparece la alternativa: la fuente de poder
        self.assertIn("falla_fuente", {dg.hecho for dg in inferencia.diagnosticos})

    def test_evidencia_a_favor_refuerza(self):
        r = equipo_sano(se_apaga_solo=True, calor_excesivo=True, ventilador_siempre_activo=True)
        self.assertEqual(diagnosticos(r), {"sobrecalentamiento": 0.93})

    def test_evidencia_a_favor_sola_no_crea_un_diagnostico(self):
        self.assertEqual(diagnosticos(equipo_sano(ventilador_siempre_activo=True)), {})

    def test_evidencia_en_contra_puede_descartar(self):
        inferencia = encadenar_hacia_adelante(
            BASE, equipo_sano(conexion_red=False, otros_dispositivos_conectan=False))
        self.assertEqual([dg.hecho for dg in inferencia.diagnosticos], ["falla_router"])
        [descartado] = inferencia.descartados
        self.assertEqual(descartado.hecho, "falla_red")
        self.assertLessEqual(descartado.certeza, UMBRAL_CERTEZA)
        self.assertEqual([d.regla.id for d in descartado.en_contra], ["E03"])

    def test_umbral(self):
        base = base_de_prueba(
            {"id": "R1", "descripcion": "d", "si": {"a": True}, "entonces": "d",
             "recomendacion": "r", "confianza": 0.3},
            {"id": "E1", "descripcion": "e", "si": {"b": True}, "entonces": "d", "confianza": -0.2},
            hechos="ab",
        )
        solo = encadenar_hacia_adelante(base, {"a": True, "b": False})
        con_contra = encadenar_hacia_adelante(base, {"a": True, "b": True})
        self.assertAlmostEqual(solo.principal.certeza, 0.3)
        self.assertEqual(con_contra.diagnosticos, [])        # (0.3 - 0.2) / 0.8 = 0.125 < 0.2
        self.assertAlmostEqual(con_contra.descartados[0].certeza, 0.125)

    def test_toda_la_evidencia_se_reune_antes_de_usar_un_hecho(self):
        # D depende de x, que tiene dos reglas; aunque D esté primera en el archivo,
        # debe usar la certeza combinada de x: 0.8 × (0.5 + 0.5 × 0.5) = 0.6
        base = base_de_prueba(
            {"id": "D", "descripcion": "d", "si": {"x": True}, "entonces": "y",
             "recomendacion": "r", "confianza": 0.8},
            {"id": "I1", "descripcion": "i1", "si": {"a": True}, "entonces": "x", "confianza": 0.5},
            {"id": "I2", "descripcion": "i2", "si": {"b": True}, "entonces": "x", "confianza": 0.5},
            hechos="ab",
        )
        self.assertAlmostEqual(encadenar_hacia_adelante(base, {"a": True, "b": True}).principal.certeza, 0.6)

    def test_el_resultado_no_depende_del_orden_de_las_reglas(self):
        azar = random.Random(11)
        dominios = {h: (e.valores_opcion if e.tipo == OPCION else (60.0, 75.0, 95.0) if e.tipo == NUMERO
                        else (True, False)) for h, e in BASE.hechos.items()}
        for _ in range(30):
            reglas = list(BASE.reglas)
            azar.shuffle(reglas)
            mezclada = BaseDeConocimiento(BASE.nombre, BASE.hechos, tuple(reglas))
            for _ in range(20):
                r = {h: azar.choice(d) for h, d in dominios.items()}
                esperado = {dg.hecho: round(dg.certeza, 9)
                            for dg in encadenar_hacia_adelante(BASE, r).diagnosticos}
                obtenido = {dg.hecho: round(dg.certeza, 9)
                            for dg in encadenar_hacia_adelante(mezclada, r).diagnosticos}
                self.assertEqual(esperado, obtenido, r)

    def test_la_consulta_pregunta_por_la_evidencia(self):
        r = {"enciende": True, "conexion_red": False, "otras_apps_funcionan": True}
        pregunta = pregunta_sobre(BASE, r, "otros_dispositivos_conectan")
        self.assertEqual({regla.id for regla in pregunta.hipotesis}, {"R16", "E03"})

    def test_validador_de_evidencia(self):
        casos = {
            "no lleva 'recomendacion'": {"id": "E1", "descripcion": "e", "si": {"a": True}, "entonces": "d",
                                         "recomendacion": "x", "confianza": -0.5},
            "solo puede apuntar a un diagnóstico": {"id": "E1", "descripcion": "e", "si": {"a": True},
                                                    "entonces": "otra_cosa", "confianza": -0.5},
            "distinto de 0": {"id": "E1", "descripcion": "e", "si": {"a": True}, "entonces": "d",
                              "confianza": 0},
            "entre -1 y 1": {"id": "E1", "descripcion": "e", "si": {"a": True}, "entonces": "d",
                             "confianza": -1.5},
        }
        diagnostico = {"id": "R1", "descripcion": "d", "si": {"b": True}, "entonces": "d",
                       "recomendacion": "r", "confianza": 0.8}
        for mensaje, evidencia in casos.items():
            with self.subTest(mensaje), self.assertRaises(ErrorDeConocimiento) as ctx:
                base_de_prueba(diagnostico, evidencia, hechos="ab")
            self.assertIn(mensaje, "\n".join(ctx.exception.errores))

    def test_no_se_puede_debilitar_un_diagnostico_usado_como_condicion(self):
        with self.assertRaises(ErrorDeConocimiento) as ctx:
            base_de_prueba(
                {"id": "R1", "descripcion": "d", "si": {"a": True}, "entonces": "d",
                 "recomendacion": "r", "confianza": 0.8},
                {"id": "R2", "descripcion": "e", "si": {"d": True, "b": True}, "entonces": "f",
                 "recomendacion": "r2", "confianza": 0.8},
                {"id": "E1", "descripcion": "c", "si": {"c": True}, "entonces": "d", "confianza": -0.5},
            )
        self.assertIn("se usa como condición", "\n".join(ctx.exception.errores))


class TestPruebasDeVerificacion(unittest.TestCase):
    def test_una_prueba_confirma(self):
        self.assertEqual(diagnosticos(respuestas(prueba_otra_fuente=True)), {"falla_fuente": 0.996})
        r = equipo_sano(hay_video=False, patron_pitidos="uno_corto", prueba_otro_monitor=True)
        self.assertEqual(diagnosticos(r), {"falla_monitor": 0.98})

    def test_una_prueba_descarta_aunque_el_sintoma_sea_fuerte(self):
        inferencia = encadenar_hacia_adelante(BASE, respuestas(prueba_otra_fuente=False))
        self.assertEqual(inferencia.diagnosticos, [])
        self.assertEqual([dg.hecho for dg in inferencia.descartados], ["falla_fuente"])

    def test_una_misma_prueba_apoya_una_causa_y_descarta_otra(self):
        # Pitido largo y cortos sugiere la tarjeta de video; si otro monitor sí da imagen, no lo es
        r = equipo_sano(hay_video=False, patron_pitidos="largo_y_cortos", prueba_otro_monitor=True)
        inferencia = encadenar_hacia_adelante(BASE, r)
        self.assertEqual([dg.hecho for dg in inferencia.descartados], ["falla_video"])
        r["prueba_otro_monitor"] = False
        self.assertAlmostEqual(diagnosticos(r)["falla_video"], 0.95)

    def test_prueba_de_opcion(self):
        base = equipo_sano(inicia_lento=True, disco_al_100=True)
        certezas = {estado: diagnosticos(dict(base, prueba_smart=estado))["falla_disco"]
                    for estado in ("malo", "precaucion", "bueno")}
        self.assertGreater(certezas["malo"], certezas["precaucion"])
        self.assertGreater(certezas["precaucion"], 0.85)          # la regla sola da 0.85
        self.assertLess(certezas["bueno"], 0.85)

    def test_las_pruebas_se_preguntan_despues_de_los_sintomas(self):
        from sistema_experto.motor import siguiente_pregunta
        verdad = equipo_sano(inicia_lento=True, disco_al_100=True, prueba_smart="malo")
        orden, r = [], {}
        while (p := siguiente_pregunta(BASE, r)) is not None:
            orden.append(BASE.hechos[p.hecho].prueba)
            r[p.hecho] = verdad[p.hecho]
        self.assertIn(True, orden)
        self.assertEqual(orden, sorted(orden), "una prueba se preguntó antes que un síntoma")

    def test_la_temperatura_solo_se_pide_si_hay_imagen(self):
        from sistema_experto.motor import siguiente_pregunta
        r = {"enciende": True, "hay_video": False}
        while (p := siguiente_pregunta(BASE, r)) is not None:
            self.assertNotEqual(p.hecho, "temperatura_cpu")
            r[p.hecho] = None

    def test_porcentaje_no_redondea_a_certeza_absoluta(self):
        from sistema_experto.modelo import porcentaje
        self.assertEqual(porcentaje(0.996), "99%")
        self.assertEqual(porcentaje(1.0), "100%")
        self.assertEqual(porcentaje(0.75), "75%")


class TestEncadenamientoHaciaAtras(unittest.TestCase):
    def test_indica_lo_que_falta(self):
        [analisis] = encadenar_hacia_atras(BASE, "R07", {"enciende": True, "se_apaga_solo": True})
        self.assertFalse(analisis.se_activa)
        self.assertFalse(analisis.descartada)
        self.assertEqual(analisis.por_preguntar, ["calor_excesivo"])

    def test_recorre_hechos_intermedios(self):
        [analisis] = encadenar_hacia_atras(BASE, "R02", {})
        self.assertEqual(analisis.por_preguntar, ["enciende", "hay_video", "patron_pitidos"])
        intermedia = analisis.condiciones[0]
        self.assertEqual(intermedia.hecho, "arranque_sin_video")
        self.assertEqual(intermedia.subobjetivos[0].regla.id, "I01")

    def test_detecta_contradiccion_en_subobjetivo(self):
        [analisis] = encadenar_hacia_atras(BASE, "R02", {"enciende": True, "hay_video": True})
        self.assertTrue(analisis.descartada)
        self.assertEqual(analisis.por_preguntar, [])

    def test_se_activa(self):
        analisis = encadenar_hacia_atras(
            BASE, "falla_ram", {"enciende": True, "hay_video": False, "patron_pitidos": "repetidos"})
        self.assertEqual([a.regla.id for a in analisis], ["R02", "E12", "E13"])
        self.assertTrue(analisis[0].se_activa)

    def test_condiciones_numericas_y_de_opcion(self):
        con_imagen = {"enciende": True, "hay_video": True}
        [alta] = encadenar_hacia_atras(BASE, "R14", {**con_imagen, "temperatura_cpu": 95})
        [normal] = encadenar_hacia_atras(BASE, "R14", {**con_imagen, "temperatura_cpu": 50})
        [laptop] = encadenar_hacia_atras(BASE, "R01", {"tipo_equipo": "laptop"})
        self.assertTrue(alta.se_activa)
        self.assertTrue(normal.descartada)
        self.assertTrue(laptop.descartada)

    def test_meta_por_hecho_devuelve_todas_sus_reglas(self):
        analisis = encadenar_hacia_atras(BASE, "sobrecalentamiento", {})
        self.assertEqual([a.regla.id for a in analisis], ["R07", "R14", "E01", "E02"])

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

    def test_exporta_los_tipos_y_las_condiciones(self):
        grafo = exportar_red(BASE)
        nodos = {n["id"]: n for n in grafo["nodos"]}
        self.assertEqual(nodos["temperatura_cpu"]["respuesta"], NUMERO)
        self.assertEqual(nodos["temperatura_cpu"]["unidad"], "°C")
        self.assertIn("laptop", nodos["tipo_equipo"]["opciones"])
        valores = {(a["origen"], a["destino"]): a.get("valor") for a in grafo["aristas"]}
        self.assertEqual(valores[("temperatura_cpu", "R14")], {">=": 90})
        self.assertEqual(valores[("patron_pitidos", "R10")], ["ninguno", "uno_corto"])
        self.assertIs(valores[("enciende", "R01")], False)
        json.dumps(grafo)   # debe poder guardarse como JSON


if __name__ == "__main__":
    unittest.main()
