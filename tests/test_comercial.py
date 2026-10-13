"""
Pruebas de los planes, el almacén de clientes y la parte comercial de la API.
Las de planes y almacén no necesitan dependencias; las de la API se omiten sin FastAPI.
"""

import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from sistema_experto.clientes import (
    Almacen,
    CuotaAgotada,
    LimitadorPorMinuto,
    huella_consulta,
)
from sistema_experto.planes import ErrorDePlanes, Plan, cargar_planes

HAY_API = (importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None
           and importlib.util.find_spec("reportlab") is not None)

FUENTE = {"enciende": False, "tipo_equipo": "escritorio", "luces_led": False,
          "interruptor_fuente_encendido": True}
CASOS = [{"enciende": False}, {"enciende": True}, {"enciende": False, "tipo_equipo": "laptop"},
         {"enciende": True, "hay_video": False}, FUENTE]


class TestPlanes(unittest.TestCase):
    def test_los_planes_por_defecto_son_los_acordados(self):
        planes = cargar_planes()
        self.assertEqual(planes["por_uso"].precio_usd, 5)
        self.assertEqual((planes["basico"].precio_usd, planes["basico"].consultas_incluidas), (10, 50))
        profesional = planes["profesional"]
        self.assertEqual((profesional.precio_usd, profesional.consultas_incluidas), (15, 150))

    def test_importe_y_restantes(self):
        planes = cargar_planes()
        self.assertEqual(planes["por_uso"].importe(7), 35)           # se cobra cada consulta
        self.assertEqual(planes["por_uso"].importe(0), 0)
        self.assertEqual(planes["basico"].importe(0), 10)            # el mensual es fijo
        self.assertEqual(planes["basico"].importe(50), 10)
        self.assertEqual(planes["basico"].restantes(20), 30)
        self.assertEqual(planes["basico"].restantes(80), 0)
        self.assertIsNone(planes["por_uso"].restantes(20))

    def escribir(self, datos) -> Path:
        carpeta = Path(tempfile.mkdtemp())
        ruta = carpeta / "planes.json"
        ruta.write_text(json.dumps(datos), encoding="utf-8")
        return ruta

    def test_un_archivo_con_errores_los_reporta_todos(self):
        ruta = self.escribir({
            "a": {"tipo": "mensual", "precio_usd": 10, "limite_por_minuto": 5},   # falta consultas_incluidas
            "b": {"tipo": "regalo", "precio_usd": -1, "limite_por_minuto": 5},
            "c": {"tipo": "por_uso", "precio_usd": 1, "limite_por_minuto": 5, "consultas_incluidas": 3,
                  "color": "rojo"},
        })
        with self.assertRaises(ErrorDePlanes) as contexto:
            cargar_planes(ruta)
        mensaje = str(contexto.exception)
        for esperado in ("a:", "b:", "c:", "consultas_incluidas", "tipo", "precio_usd", "color"):
            self.assertIn(esperado, mensaje)

    def test_se_puede_cambiar_el_precio_sin_tocar_codigo(self):
        ruta = self.escribir({"solo": {"tipo": "por_uso", "precio_usd": 2.5, "limite_por_minuto": 10}})
        self.assertEqual(cargar_planes(ruta)["solo"].importe(4), 10)


class TestAlmacen(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)
        self.bd = Almacen(Path(self.carpeta.name) / "datos" / "clientes.db")   # crea la carpeta que falte

    def test_crear_cliente_y_buscar_por_clave(self):
        cliente, clave = self.bd.crear_cliente("Taller Los Pinos", "basico")
        self.assertTrue(clave.startswith("se_"))
        self.assertEqual(self.bd.buscar_por_clave(clave), cliente)
        self.assertIsNone(self.bd.buscar_por_clave(clave + "x"))
        self.assertIsNone(self.bd.buscar_por_clave(""))

    def test_la_clave_no_se_guarda_en_claro(self):
        _, clave = self.bd.crear_cliente("Taller", "basico")
        with closing(sqlite3.connect(self.bd.ruta)) as conexion:
            volcado = "\n".join(conexion.iterdump())
        self.assertNotIn(clave, volcado)

    def test_revocar_una_clave(self):
        cliente, clave = self.bd.crear_cliente("Taller", "basico")
        otra = self.bd.nueva_clave(cliente.id)
        self.assertTrue(self.bd.revocar_clave(clave[:11]))
        self.assertIsNone(self.bd.buscar_por_clave(clave))
        self.assertEqual(self.bd.buscar_por_clave(otra), cliente)       # la otra sigue funcionando
        self.assertFalse(self.bd.revocar_clave(clave[:11]))             # ya estaba revocada

    def test_la_misma_consulta_se_cuenta_una_vez_al_mes(self):
        cliente, _ = self.bd.crear_cliente("Taller", "basico")
        huella = huella_consulta(FUENTE)
        self.assertEqual(self.bd.registrar_consulta(cliente.id, huella, "2026-10"), (True, 1))
        self.assertEqual(self.bd.registrar_consulta(cliente.id, huella, "2026-10"), (False, 1))
        self.assertEqual(self.bd.registrar_consulta(cliente.id, huella, "2026-11"), (True, 1))   # otro mes
        self.assertEqual(self.bd.consumo(cliente.id, "2026-10"), 1)

    def test_el_orden_de_las_respuestas_no_cambia_la_consulta(self):
        self.assertEqual(huella_consulta({"a": True, "b": False}), huella_consulta({"b": False, "a": True}))
        self.assertNotEqual(huella_consulta({"a": True}), huella_consulta({"a": False}))
        self.assertNotEqual(huella_consulta({"a": None}), huella_consulta({}))

    def test_el_tope_corta_las_consultas_nuevas_pero_no_las_repetidas(self):
        cliente, _ = self.bd.crear_cliente("Taller", "mini")
        for caso in CASOS[:2]:
            self.bd.registrar_consulta(cliente.id, huella_consulta(caso), "2026-10", tope=2)
        with self.assertRaises(CuotaAgotada):
            self.bd.registrar_consulta(cliente.id, huella_consulta(CASOS[2]), "2026-10", tope=2)
        self.assertEqual(self.bd.consumo(cliente.id, "2026-10"), 2)      # la rechazada no se contó
        nueva, _ = self.bd.registrar_consulta(cliente.id, huella_consulta(CASOS[0]), "2026-10", tope=2)
        self.assertFalse(nueva)                                # repetir una ya contada sigue valiendo

    def test_el_consumo_es_por_cliente(self):
        a, _ = self.bd.crear_cliente("A", "basico")
        b, _ = self.bd.crear_cliente("B", "basico")
        self.bd.registrar_consulta(a.id, huella_consulta(FUENTE), "2026-10")
        self.assertEqual(self.bd.consumo_por_cliente("2026-10"), {a.id: 1})
        self.assertEqual(self.bd.consumo(b.id, "2026-10"), 0)


class TestLimitador(unittest.TestCase):
    def test_deja_pasar_hasta_el_limite_y_luego_pide_esperar(self):
        limitador = LimitadorPorMinuto()
        self.assertIsNone(limitador.permitir(1, 2, 100.0))
        self.assertIsNone(limitador.permitir(1, 2, 101.0))
        espera = limitador.permitir(1, 2, 102.0)
        self.assertIsNotNone(espera)
        self.assertTrue(1 <= espera <= 60)

    def test_la_ventana_se_libera_con_el_tiempo(self):
        limitador = LimitadorPorMinuto()
        limitador.permitir(1, 1, 100.0)
        self.assertIsNotNone(limitador.permitir(1, 1, 130.0))
        self.assertIsNone(limitador.permitir(1, 1, 161.0))

    def test_cada_cliente_tiene_su_ventana(self):
        limitador = LimitadorPorMinuto()
        limitador.permitir(1, 1, 100.0)
        self.assertIsNone(limitador.permitir(2, 1, 100.0))


@unittest.skipUnless(HAY_API, "Faltan FastAPI, httpx o reportlab (pip install -r requirements-api.txt)")
class TestApiComercial(unittest.TestCase):
    ADMIN = {"X-Admin-Key": "admin-secreta"}

    def setUp(self):
        from fastapi.testclient import TestClient

        from sistema_experto import comercial
        from sistema_experto.api import app
        self.comercial = comercial
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)
        self.mes = [datetime(2026, 10, 13, tzinfo=timezone.utc)]
        self.segundos = [1000.0]
        entorno = mock.patch.dict(os.environ, {
            "SISTEMA_EXPERTO_ADMIN_KEY": "admin-secreta",
            "SISTEMA_EXPERTO_BD": str(Path(self.carpeta.name) / "clientes.db"),
            "SISTEMA_EXPERTO_API_KEYS": "",
        })
        planes = mock.patch.dict(comercial.PLANES, {"mini": Plan("mini", "Mini", "mensual", 1, 2, 60)})
        # patch.object en vez de mock.patch("...") para no depender del orden de importación
        parches = [entorno, planes,
                   mock.patch.object(comercial, "ahora", lambda: self.mes[0]),
                   mock.patch.object(comercial, "reloj", lambda: self.segundos[0]),
                   mock.patch.object(comercial, "_limitador", LimitadorPorMinuto())]
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        self.web = TestClient(app)

    def alta(self, nombre="Taller", plan="basico") -> tuple[int, dict]:
        r = self.web.post("/admin/clientes", json={"nombre": nombre, "plan": plan}, headers=self.ADMIN)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"], {"X-API-Key": r.json()["clave"]}

    def resultado(self, claves, respuestas=FUENTE):
        return self.web.post("/v1/consulta/resultado", json={"respuestas": respuestas}, headers=claves)

    # ── Acceso ──

    def test_en_modo_comercial_se_exige_la_clave_de_un_cliente(self):
        self.assertEqual(self.web.get("/v1/conocimiento").status_code, 401)
        inventada = {"X-API-Key": "se_inventada"}
        self.assertEqual(self.web.get("/v1/conocimiento", headers=inventada).status_code, 401)
        _, claves = self.alta()
        self.assertEqual(self.web.get("/v1/conocimiento", headers=claves).status_code, 200)
        self.assertEqual(self.web.get("/salud").status_code, 200)

    def test_sin_clave_de_administracion_no_existe_la_administracion(self):
        with mock.patch.dict(os.environ, {"SISTEMA_EXPERTO_ADMIN_KEY": ""}):
            self.assertEqual(self.web.get("/admin/clientes", headers=self.ADMIN).status_code, 404)
            self.assertEqual(self.web.get("/v1/uso").status_code, 404)    # el modo abierto no tiene cuentas

    def test_la_administracion_pide_su_propia_clave(self):
        self.assertEqual(self.web.get("/admin/clientes").status_code, 403)
        self.assertEqual(self.web.get("/admin/clientes", headers={"X-Admin-Key": "otra"}).status_code, 403)
        _, claves = self.alta()
        de_cliente = self.web.get("/admin/clientes", headers=claves)
        self.assertEqual(de_cliente.status_code, 403)          # una clave de cliente no administra

    def test_cuenta_suspendida_y_clave_revocada(self):
        cliente_id, claves = self.alta()
        self.web.put(f"/admin/clientes/{cliente_id}", json={"activo": False}, headers=self.ADMIN)
        self.assertEqual(self.resultado(claves).status_code, 403)
        self.web.put(f"/admin/clientes/{cliente_id}", json={"activo": True}, headers=self.ADMIN)
        self.assertEqual(self.resultado(claves).status_code, 200)
        self.web.delete(f"/admin/claves/{claves['X-API-Key'][:11]}", headers=self.ADMIN)
        self.assertEqual(self.resultado(claves).status_code, 401)

    def test_rotar_la_clave(self):
        cliente_id, vieja = self.alta()
        nueva = {"X-API-Key": self.web.post(f"/admin/clientes/{cliente_id}/claves",
                                            headers=self.ADMIN).json()["clave"]}
        self.assertEqual(self.resultado(vieja).status_code, 200)         # conviven hasta revocar la vieja
        self.assertEqual(self.resultado(nueva).status_code, 200)

    # ── Consumo ──

    def test_cada_diagnostico_distinto_cuenta_y_se_informa_en_las_cabeceras(self):
        _, claves = self.alta(plan="basico")
        r = self.resultado(claves, CASOS[0])
        self.assertEqual((r.headers["x-consultas-usadas"], r.headers["x-consultas-restantes"]), ("1", "49"))
        r = self.resultado(claves, CASOS[1])
        self.assertEqual((r.headers["x-consultas-usadas"], r.headers["x-consultas-restantes"]), ("2", "48"))

    def test_repetir_la_consulta_o_pedir_su_informe_no_cobra_otra_vez(self):
        cliente_id, claves = self.alta(plan="por_uso")
        self.resultado(claves)
        self.resultado(claves)
        informe = self.web.post("/v1/consulta/informe", json={"respuestas": FUENTE}, headers=claves)
        self.assertEqual(informe.status_code, 200)
        self.assertTrue(informe.content.startswith(b"%PDF"))
        self.assertEqual(self.web.get("/v1/uso", headers=claves).json()["consultas"], 1)

    def test_el_informe_de_un_diagnostico_nuevo_si_cuenta(self):
        _, claves = self.alta(plan="por_uso")
        informe = self.web.post("/v1/consulta/informe", json={"respuestas": FUENTE}, headers=claves)
        self.assertEqual(informe.headers["x-consultas-usadas"], "1")

    def test_preguntar_no_cuenta(self):
        _, claves = self.alta(plan="mini")
        for _ in range(10):
            self.web.post("/v1/consulta/siguiente", json={"respuestas": {}}, headers=claves)
        self.assertEqual(self.web.get("/v1/uso", headers=claves).json()["consultas"], 0)

    def test_un_pedido_rechazado_no_cuenta(self):
        _, claves = self.alta(plan="mini")
        self.assertEqual(self.resultado(claves, {"inventado": True}).status_code, 422)
        self.assertEqual(self.web.get("/v1/uso", headers=claves).json()["consultas"], 0)

    def test_al_agotar_la_cuota_responde_402_y_se_renueva_al_mes_siguiente(self):
        _, claves = self.alta(plan="mini")                               # 2 consultas incluidas
        self.assertEqual(self.resultado(claves, CASOS[0]).status_code, 200)
        self.assertEqual(self.resultado(claves, CASOS[1]).status_code, 200)
        agotada = self.resultado(claves, CASOS[2])
        self.assertEqual(agotada.status_code, 402)
        self.assertIn("2 consultas", agotada.json()["detail"])
        self.assertNotIn("diagnosticos", agotada.json())                 # no se entrega el diagnóstico
        self.assertEqual(self.resultado(claves, CASOS[0]).status_code, 200)    # repetir una contada vale
        informe = self.web.post("/v1/consulta/informe", json={"respuestas": CASOS[2]}, headers=claves)
        self.assertEqual(informe.status_code, 402)                       # el PDF tampoco se salta la cuota
        self.mes[0] = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.assertEqual(self.resultado(claves, CASOS[2]).status_code, 200)

    def test_el_plan_por_uso_no_tiene_tope_mensual(self):
        _, claves = self.alta(plan="por_uso")
        for caso in CASOS:
            self.assertEqual(self.resultado(claves, caso).status_code, 200)
        self.assertNotIn("x-consultas-restantes", self.resultado(claves, CASOS[0]).headers)

    def test_limite_por_minuto(self):
        self.comercial.PLANES["mini"] = Plan("mini", "Mini", "mensual", 1, 2, 3)   # 3 llamadas por minuto
        _, claves = self.alta(plan="mini")
        estados = [self.web.get("/v1/conocimiento", headers=claves).status_code for _ in range(4)]
        self.assertEqual(estados, [200, 200, 200, 429])
        limitado = self.web.get("/v1/conocimiento", headers=claves)
        self.assertIn("retry-after", limitado.headers)
        self.segundos[0] += 61
        self.assertEqual(self.web.get("/v1/conocimiento", headers=claves).status_code, 200)

    def test_el_limite_de_un_cliente_no_afecta_a_otro(self):
        self.comercial.PLANES["mini"] = Plan("mini", "Mini", "mensual", 1, 2, 1)
        _, uno = self.alta("Uno", "mini")
        _, otro = self.alta("Otro", "mini")
        self.web.get("/v1/conocimiento", headers=uno)
        self.assertEqual(self.web.get("/v1/conocimiento", headers=uno).status_code, 429)
        self.assertEqual(self.web.get("/v1/conocimiento", headers=otro).status_code, 200)

    # ── Cuenta y facturación ──

    def test_uso_del_cliente(self):
        _, claves = self.alta(plan="basico")
        self.resultado(claves, CASOS[0])
        uso = self.web.get("/v1/uso", headers=claves).json()
        self.assertEqual((uso["plan"], uso["periodo"], uso["consultas"], uso["incluidas"], uso["restantes"]),
                         ("basico", "2026-10", 1, 50, 49))
        self.assertEqual(uso["importe_usd"], 10)

    def test_facturacion_del_mes(self):
        _, uno = self.alta("Por uso", "por_uso")
        _, dos = self.alta("Basico", "basico")
        self.alta("Profesional sin uso", "profesional")
        self.alta("Por uso sin uso", "por_uso")
        for caso in CASOS[:3]:
            self.resultado(uno, caso)
        self.resultado(dos, CASOS[0])
        factura = self.web.get("/admin/facturacion", headers=self.ADMIN).json()
        importes = {f["cliente"]: f["importe_usd"] for f in factura["clientes"]}
        self.assertEqual(importes, {"Por uso": 15, "Basico": 10, "Profesional sin uso": 15})
        self.assertEqual(factura["total_usd"], 40)
        self.assertEqual(factura["periodo"], "2026-10")
        otro_mes = self.web.get("/admin/facturacion?periodo=2026-09", headers=self.ADMIN).json()
        self.assertEqual({f["cliente"] for f in otro_mes["clientes"]}, {"Basico", "Profesional sin uso"})

    def test_facturacion_con_periodo_invalido(self):
        for periodo in ("octubre", "2026-13", "2026-1", "26-10"):
            r = self.web.get(f"/admin/facturacion?periodo={periodo}", headers=self.ADMIN)
            self.assertEqual(r.status_code, 422, periodo)

    def test_cliente_suspendido_con_consumo_se_factura_pero_sin_consumo_no(self):
        activo_id, claves = self.alta("Con consumo", "basico")
        self.resultado(claves)
        quieto_id, _ = self.alta("Sin consumo", "basico")
        for cliente_id in (activo_id, quieto_id):
            self.web.put(f"/admin/clientes/{cliente_id}", json={"activo": False}, headers=self.ADMIN)
        factura = self.web.get("/admin/facturacion", headers=self.ADMIN).json()
        nombres = {f["cliente"] for f in factura["clientes"]}
        self.assertEqual(nombres, {"Con consumo"})

    def test_listado_de_clientes_muestra_prefijos_y_nunca_la_clave_completa(self):
        _, claves = self.alta("Taller", "basico")
        self.resultado(claves)
        texto = self.web.get("/admin/clientes", headers=self.ADMIN).text
        self.assertNotIn(claves["X-API-Key"], texto)
        self.assertIn(claves["X-API-Key"][:11], texto)
        [cliente] = json.loads(texto)
        self.assertEqual((cliente["consultas"], cliente["activo"]), (1, True))

    def test_validaciones_de_administracion(self):
        r = self.web.post("/admin/clientes", json={"nombre": "X", "plan": "gratis"}, headers=self.ADMIN)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.web.post("/admin/clientes", json={"nombre": "", "plan": "basico"},
                                       headers=self.ADMIN).status_code, 422)
        self.assertEqual(self.web.put("/admin/clientes/999", json={"activo": False},
                                      headers=self.ADMIN).status_code, 404)
        cliente_id, _ = self.alta()
        self.assertEqual(self.web.put(f"/admin/clientes/{cliente_id}", json={"plan": "gratis"},
                                      headers=self.ADMIN).status_code, 422)
        self.assertEqual(self.web.delete("/admin/claves/se_noexiste", headers=self.ADMIN).status_code, 404)

    def test_cambiar_de_plan_aplica_la_nueva_cuota(self):
        cliente_id, claves = self.alta(plan="mini")
        self.resultado(claves, CASOS[0])
        self.resultado(claves, CASOS[1])
        self.assertEqual(self.resultado(claves, CASOS[2]).status_code, 402)
        self.web.put(f"/admin/clientes/{cliente_id}", json={"plan": "profesional"}, headers=self.ADMIN)
        self.assertEqual(self.resultado(claves, CASOS[2]).status_code, 200)

    def test_modo_abierto_sigue_funcionando_como_antes(self):
        abierto = {"SISTEMA_EXPERTO_ADMIN_KEY": "", "SISTEMA_EXPERTO_API_KEYS": "vieja"}
        with mock.patch.dict(os.environ, abierto):
            self.assertEqual(self.web.get("/v1/conocimiento").status_code, 401)
            ok = self.web.post("/v1/consulta/resultado", json={"respuestas": FUENTE},
                               headers={"X-API-Key": "vieja"})
            self.assertEqual(ok.status_code, 200)
            self.assertNotIn("x-consultas-usadas", ok.headers)           # sin cuentas, sin conteo


if __name__ == "__main__":
    unittest.main()
