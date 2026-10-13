"""
Clientes del servicio: quién puede llamar a la API, con qué plan y cuántas consultas lleva en el mes.

Usa SQLite (biblioteca estándar, sin dependencias). Las claves se guardan como huella SHA-256, nunca en claro:
la clave completa solo se muestra una vez, al crearla. Son aleatorias y largas, por eso basta una huella
rápida (no hace falta bcrypt como en las contraseñas).

Una *consulta* facturable es un diagnóstico entregado (`/resultado` o `/informe`). Se cuenta una vez por
cliente, mes y conjunto de respuestas: pedir el PDF de un diagnóstico que ya se consultó, o repetir la misma
consulta, no cobra otra vez.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
from collections import defaultdict, deque
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "datos" / "clientes.db"
PREFIJO_CLAVE = "se_"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL,
    plan    TEXT NOT NULL,
    activo  INTEGER NOT NULL DEFAULT 1,
    creado  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claves (
    huella     TEXT PRIMARY KEY,
    prefijo    TEXT NOT NULL UNIQUE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    activa     INTEGER NOT NULL DEFAULT 1,
    creada     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consumos (
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    periodo    TEXT NOT NULL,
    consulta   TEXT NOT NULL,
    creado     TEXT NOT NULL,
    PRIMARY KEY (cliente_id, periodo, consulta)
);
"""


class CuotaAgotada(Exception):
    """El cliente ya usó todas las consultas que incluye su plan este mes."""

    def __init__(self, incluidas: int) -> None:
        super().__init__(f"Se agotaron las {incluidas} consultas incluidas en tu plan este mes.")
        self.incluidas = incluidas


@dataclass(frozen=True)
class Cliente:
    id: int
    nombre: str
    plan: str
    activo: bool


def ahora() -> datetime:
    """Reloj del servicio (las pruebas lo reemplazan)."""
    return datetime.now(timezone.utc)


def periodo_de(momento: datetime) -> str:
    return momento.strftime("%Y-%m")


def huella_clave(clave: str) -> str:
    return hashlib.sha256(clave.encode()).hexdigest()


def huella_consulta(respuestas: Mapping[str, object]) -> str:
    """Identifica una consulta por sus respuestas, sin importar el orden en que llegaron."""
    canonico = json.dumps(sorted(respuestas.items()), ensure_ascii=False, default=str)
    return hashlib.sha256(canonico.encode()).hexdigest()


class Almacen:
    """Base de datos de clientes, claves y consumo."""

    def __init__(self, ruta: str | Path | None = None) -> None:
        self.ruta = Path(ruta or os.environ.get("SISTEMA_EXPERTO_BD") or RUTA_POR_DEFECTO)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as bd:
            bd.executescript(ESQUEMA)

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        # una conexión por operación: FastAPI atiende cada petición en un hilo distinto
        bd = sqlite3.connect(self.ruta, timeout=10, isolation_level=None)
        bd.row_factory = sqlite3.Row
        try:
            bd.execute("PRAGMA journal_mode=WAL")
            bd.execute("PRAGMA foreign_keys=ON")
            yield bd
        finally:
            bd.close()

    # ── Altas y bajas ──

    def crear_cliente(self, nombre: str, plan: str) -> tuple[Cliente, str]:
        """Da de alta a un cliente y devuelve su primera clave (única vez que se ve completa)."""
        with self._conexion() as bd:
            cursor = bd.execute("INSERT INTO clientes (nombre, plan, creado) VALUES (?, ?, ?)",
                                (nombre, plan, ahora().isoformat()))
            cliente_id = cursor.lastrowid
        return self.cliente(cliente_id), self.nueva_clave(cliente_id)

    def nueva_clave(self, cliente_id: int) -> str:
        clave = PREFIJO_CLAVE + secrets.token_urlsafe(32)
        with self._conexion() as bd:
            bd.execute("INSERT INTO claves (huella, prefijo, cliente_id, creada) VALUES (?, ?, ?, ?)",
                       (huella_clave(clave), clave[:11], cliente_id, ahora().isoformat()))
        return clave

    def revocar_clave(self, prefijo: str) -> bool:
        with self._conexion() as bd:
            return bd.execute("UPDATE claves SET activa = 0 WHERE prefijo = ? AND activa = 1",
                              (prefijo,)).rowcount > 0

    def cambiar(self, cliente_id: int, plan: str | None = None, activo: bool | None = None) -> None:
        with self._conexion() as bd:
            if plan is not None:
                bd.execute("UPDATE clientes SET plan = ? WHERE id = ?", (plan, cliente_id))
            if activo is not None:
                bd.execute("UPDATE clientes SET activo = ? WHERE id = ?", (int(activo), cliente_id))

    # ── Consultas ──

    def cliente(self, cliente_id: int) -> Cliente | None:
        with self._conexion() as bd:
            fila = bd.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
        return _cliente(fila) if fila else None

    def buscar_por_clave(self, clave: str) -> Cliente | None:
        """El cliente dueño de una clave activa (activo o no: quien llama decide qué hacer)."""
        with self._conexion() as bd:
            fila = bd.execute(
                "SELECT c.* FROM claves k JOIN clientes c ON c.id = k.cliente_id "
                "WHERE k.huella = ? AND k.activa = 1", (huella_clave(clave),)).fetchone()
        return _cliente(fila) if fila else None

    def claves(self, cliente_id: int) -> list[dict]:
        with self._conexion() as bd:
            filas = bd.execute("SELECT prefijo, activa, creada FROM claves "
                               "WHERE cliente_id = ? ORDER BY creada", (cliente_id,)).fetchall()
        return [{"prefijo": f["prefijo"], "activa": bool(f["activa"]), "creada": f["creada"]} for f in filas]

    def clientes(self) -> list[Cliente]:
        with self._conexion() as bd:
            return [_cliente(f) for f in bd.execute("SELECT * FROM clientes ORDER BY id")]

    # ── Consumo ──

    def consumo(self, cliente_id: int, periodo: str) -> int:
        with self._conexion() as bd:
            return bd.execute("SELECT COUNT(*) FROM consumos WHERE cliente_id = ? AND periodo = ?",
                              (cliente_id, periodo)).fetchone()[0]

    def registrar_consulta(self, cliente_id: int, huella: str, periodo: str,
                           tope: int | None = None) -> tuple[bool, int]:
        """
        Cuenta una consulta. Devuelve (era_nueva, consultas_del_mes). Si ya estaba contada este mes no
        cobra de nuevo. Con `tope`, lanza CuotaAgotada si una consulta nueva lo superaría. La revisión y el
        alta ocurren en una sola transacción, así dos peticiones simultáneas no se cuelan por encima del tope.
        """
        with self._conexion() as bd:
            bd.execute("BEGIN IMMEDIATE")
            try:
                ya = bd.execute("SELECT 1 FROM consumos "
                                "WHERE cliente_id = ? AND periodo = ? AND consulta = ?",
                                (cliente_id, periodo, huella)).fetchone()
                usadas = bd.execute("SELECT COUNT(*) FROM consumos WHERE cliente_id = ? AND periodo = ?",
                                    (cliente_id, periodo)).fetchone()[0]
                if ya:
                    bd.execute("COMMIT")
                    return False, usadas
                if tope is not None and usadas >= tope:
                    raise CuotaAgotada(tope)
                bd.execute("INSERT INTO consumos (cliente_id, periodo, consulta, creado) VALUES (?, ?, ?, ?)",
                           (cliente_id, periodo, huella, ahora().isoformat()))
                bd.execute("COMMIT")
                return True, usadas + 1
            except BaseException:
                bd.execute("ROLLBACK")
                raise

    def consumo_por_cliente(self, periodo: str) -> dict[int, int]:
        with self._conexion() as bd:
            filas = bd.execute("SELECT cliente_id, COUNT(*) AS n FROM consumos WHERE periodo = ? "
                               "GROUP BY cliente_id", (periodo,)).fetchall()
        return {f["cliente_id"]: f["n"] for f in filas}


def _cliente(fila: sqlite3.Row) -> Cliente:
    return Cliente(fila["id"], fila["nombre"], fila["plan"], bool(fila["activo"]))


class LimitadorPorMinuto:
    """
    Ventana deslizante de 60 s por cliente, en memoria. Con varios procesos cada uno cuenta aparte; para
    escalar a varios servidores habría que moverlo a Redis.
    """

    def __init__(self) -> None:
        self._llamadas: defaultdict[int, deque[float]] = defaultdict(deque)
        self._cerrojo = threading.Lock()

    def permitir(self, cliente_id: int, limite: int, instante: float) -> int | None:
        """None si la llamada pasa; si no, los segundos que faltan para poder llamar otra vez."""
        with self._cerrojo:
            ventana = self._llamadas[cliente_id]
            while ventana and instante - ventana[0] >= 60:
                ventana.popleft()
            if len(ventana) >= limite:
                return max(1, int(60 - (instante - ventana[0])) + 1)
            ventana.append(instante)
            return None
