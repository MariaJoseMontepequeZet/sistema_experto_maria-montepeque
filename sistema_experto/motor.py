"""
Motor de inferencia.

No sabe nada de computadoras ni imprime nada: recibe una base de
conocimiento y respuestas, y devuelve estructuras de datos que la
interfaz (cli.py u otra) decide cómo mostrar.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from .modelo import BaseDeConocimiento, BaseDeHechos, Regla

# hecho de entrada -> True (sí), False (no) o None (no sé)
Respuestas = Mapping[str, bool | None]

# ──────────────────────────────────────────────────────────────
# Encadenamiento hacia adelante
# ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Disparo:
    """Registro de una regla ejecutada en un ciclo del motor."""
    ciclo: int
    regla: Regla
    certeza: float                    # confianza de la regla × certeza de sus premisas
    conflict_set: tuple[str, ...]     # reglas candidatas en ese ciclo


@dataclass(frozen=True)
class Diagnostico:
    hecho: str
    certeza: float                    # combinada si varias reglas llegan al mismo hecho
    disparos: tuple[Disparo, ...]

    @property
    def descripcion(self) -> str:
        return self.disparos[0].regla.descripcion

    @property
    def recomendaciones(self) -> list[str]:
        return [d.regla.recomendacion for d in self.disparos if d.regla.recomendacion]

    @property
    def advertencias(self) -> list[str]:
        return list(dict.fromkeys(d.regla.advertencia for d in self.disparos
                                  if d.regla.advertencia))


@dataclass
class Inferencia:
    hechos: BaseDeHechos
    disparos: list[Disparo] = field(default_factory=list)

    @property
    def diagnosticos(self) -> list[Diagnostico]:
        """Diagnósticos ordenados de mayor a menor certeza (desempate: especificidad)."""
        por_hecho: dict[str, list[Disparo]] = {}
        for d in self.disparos:
            if d.regla.es_diagnostico:
                por_hecho.setdefault(d.regla.conclusion, []).append(d)
        diagnosticos = [
            Diagnostico(hecho, self.hechos.certeza[hecho], tuple(ds))
            for hecho, ds in por_hecho.items()
        ]
        return sorted(
            diagnosticos,
            key=lambda dg: (dg.certeza, max(d.regla.especificidad for d in dg.disparos)),
            reverse=True,
        )

    @property
    def principal(self) -> Diagnostico | None:
        diagnosticos = self.diagnosticos
        return diagnosticos[0] if diagnosticos else None

    def justificacion(self, hecho: str) -> list[Disparo]:
        """Cadena de disparos que llevó a `hecho`, en orden de ejecución."""
        necesarios: set[str] = set()
        pendientes = [hecho]
        while pendientes:
            actual = pendientes.pop()
            for d in self.disparos:
                if d.regla.conclusion == actual and d.regla.id not in necesarios:
                    necesarios.add(d.regla.id)
                    pendientes.extend(d.regla.condiciones)
        return [d for d in self.disparos if d.regla.id in necesarios]


def equiparar(reglas: Iterable[Regla], hechos: BaseDeHechos,
              disparadas: set[str] | None = None) -> list[Regla]:
    """
    Pattern matching: reglas cuyas condiciones se cumplen y que todavía no
    se dispararon (refracción: cada regla se ejecuta como máximo una vez).
    """
    disparadas = disparadas or set()
    return [r for r in reglas if r.id not in disparadas and hechos.cumple(r.condiciones)]


def resolver_conflictos(conflict_set: list[Regla]) -> Regla | None:
    """Mayor confianza primero; desempate por regla más específica."""
    if not conflict_set:
        return None
    return max(conflict_set, key=lambda r: (r.confianza, r.especificidad))


def encadenar_hacia_adelante(base: BaseDeConocimiento,
                             respuestas: Respuestas) -> Inferencia:
    """
    Ciclo reconocer-actuar hasta punto fijo:
      equiparar → resolver conflictos → disparar (afirmar la conclusión)
    Los hechos derivados alimentan a otras reglas en ciclos posteriores.
    Las respuestas "no sé" (None) dejan el hecho como desconocido.
    """
    desconocidos = set(respuestas) - set(base.preguntas)
    if desconocidos:
        raise ValueError(f"Hechos de entrada desconocidos: {sorted(desconocidos)}")

    hechos = BaseDeHechos()
    for hecho, valor in respuestas.items():
        if valor is not None:
            hechos.afirmar(hecho, valor)

    inferencia = Inferencia(hechos)
    disparadas: set[str] = set()
    ciclo = 0
    while True:
        conflict_set = equiparar(base.reglas, hechos, disparadas)
        regla = resolver_conflictos(conflict_set)
        if regla is None:
            return inferencia
        ciclo += 1
        certeza = regla.confianza * hechos.certeza_minima(regla.condiciones)
        hechos.afirmar(regla.conclusion, True, certeza, origen=regla.id)
        disparadas.add(regla.id)
        inferencia.disparos.append(
            Disparo(ciclo, regla, certeza, tuple(r.id for r in conflict_set))
        )


# ──────────────────────────────────────────────────────────────
# Encadenamiento hacia atrás
# ──────────────────────────────────────────────────────────────

CUMPLIDA, CONTRADICHA, PENDIENTE = "cumplida", "contradicha", "pendiente"


@dataclass(frozen=True)
class EstadoCondicion:
    hecho: str
    esperado: bool
    actual: bool | None
    subobjetivos: tuple[AnalisisRegla, ...] = ()   # reglas que podrían derivar el hecho

    @property
    def estado(self) -> str:
        if self.actual is None:
            return PENDIENTE
        return CUMPLIDA if self.actual == self.esperado else CONTRADICHA


@dataclass(frozen=True)
class AnalisisRegla:
    regla: Regla
    condiciones: tuple[EstadoCondicion, ...]

    @property
    def se_activa(self) -> bool:
        return all(c.estado == CUMPLIDA for c in self.condiciones)

    @property
    def descartada(self) -> bool:
        return any(c.estado == CONTRADICHA for c in self.condiciones)

    @property
    def por_preguntar(self) -> list[str]:
        """Hechos de entrada que faltan confirmar para poder activar la regla."""
        if self.descartada:
            return []
        faltan: list[str] = []
        for c in self.condiciones:
            if c.estado != PENDIENTE:
                continue
            if not c.subobjetivos:
                faltan.append(c.hecho)
            for sub in c.subobjetivos:
                faltan.extend(h for h in sub.por_preguntar if h not in faltan)
        return list(dict.fromkeys(faltan))


def buscar_metas(base: BaseDeConocimiento, meta: str) -> list[Regla]:
    """Acepta un ID de regla, su descripción o el nombre del hecho que concluye."""
    meta_normalizada = meta.strip().upper()
    return [
        r for r in base.reglas
        if meta_normalizada in (r.id.upper(), r.descripcion.upper(), r.conclusion.upper())
    ]


def encadenar_hacia_atras(base: BaseDeConocimiento, meta: str,
                          respuestas: Respuestas) -> list[AnalisisRegla]:
    """
    Parte de una hipótesis y determina recursivamente qué condiciones ya se
    cumplen, cuáles la contradicen y qué falta preguntar para confirmarla.
    """
    reglas = buscar_metas(base, meta)
    if not reglas:
        raise LookupError(f"No se encontró ninguna regla con id/descripción/hecho '{meta}'")
    return [_analizar(base, r, respuestas, frozenset()) for r in reglas]


# ──────────────────────────────────────────────────────────────
# Consulta dinámica (preguntas dirigidas por hipótesis)
# ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Pregunta:
    hecho: str
    texto: str
    hipotesis: tuple[Regla, ...]   # diagnósticos que esta respuesta ayuda a confirmar o descartar


def hipotesis_abiertas(base: BaseDeConocimiento, respuestas: Respuestas) -> list[AnalisisRegla]:
    """
    Diagnósticos que todavía pueden activarse y para los que queda alguna
    pregunta sin hacer. Los descartados, los ya confirmados y los que solo
    dependen de respuestas "no sé" quedan fuera.
    """
    abiertas = []
    for regla in base.reglas:
        if not regla.es_diagnostico:
            continue
        analisis = _analizar(base, regla, respuestas, frozenset())
        if any(h not in respuestas for h in analisis.por_preguntar):
            abiertas.append(analisis)
    return abiertas


def siguiente_pregunta(base: BaseDeConocimiento, respuestas: Respuestas) -> Pregunta | None:
    """
    Elige la pregunta que más hipótesis abiertas necesitan (así cada respuesta
    confirma o descarta la mayor cantidad posible). Desempata por la confianza
    de las hipótesis y luego por el orden del archivo de conocimiento.
    Devuelve None cuando ya no queda nada útil por preguntar.
    """
    interesadas = _hipotesis_por_hecho(base, respuestas)
    if not interesadas:
        return None

    orden = list(base.preguntas)
    hecho = max(
        interesadas,
        key=lambda h: (len(interesadas[h]),
                       max(r.confianza for r in interesadas[h]),
                       -orden.index(h)),
    )
    return pregunta_sobre(base, respuestas, hecho, interesadas)


def pregunta_sobre(base: BaseDeConocimiento, respuestas: Respuestas, hecho: str,
                   interesadas: dict[str, list[Regla]] | None = None) -> Pregunta:
    """Arma la pregunta de un hecho con las hipótesis abiertas que dependen de él."""
    if interesadas is None:
        interesadas = _hipotesis_por_hecho(base, respuestas)
    hipotesis = sorted(interesadas.get(hecho, []), key=lambda r: r.confianza, reverse=True)
    return Pregunta(hecho, base.preguntas[hecho], tuple(hipotesis))


def _hipotesis_por_hecho(base: BaseDeConocimiento,
                         respuestas: Respuestas) -> dict[str, list[Regla]]:
    interesadas: dict[str, list[Regla]] = {}
    for analisis in hipotesis_abiertas(base, respuestas):
        for hecho in analisis.por_preguntar:
            if hecho not in respuestas:
                interesadas.setdefault(hecho, []).append(analisis.regla)
    return interesadas


def _analizar(base: BaseDeConocimiento, regla: Regla,
              respuestas: Respuestas, camino: frozenset[str]) -> AnalisisRegla:
    camino = camino | {regla.id}
    estados = []
    for hecho, esperado in regla.condiciones.items():
        derivadoras = [r for r in base.reglas_que_concluyen(hecho) if r.id not in camino]
        if not derivadoras:
            estados.append(EstadoCondicion(hecho, esperado, respuestas.get(hecho)))
            continue
        subs = tuple(_analizar(base, r, respuestas, camino) for r in derivadoras)
        if any(s.se_activa for s in subs):
            actual = True
        elif all(s.descartada for s in subs):
            actual = False
        else:
            actual = None
        estados.append(EstadoCondicion(hecho, esperado, actual, subs))
    return AnalisisRegla(regla, tuple(estados))


# ──────────────────────────────────────────────────────────────
# Exportación de la red de inferencia
# ──────────────────────────────────────────────────────────────

def exportar_red(base: BaseDeConocimiento) -> dict:
    """
    Grafo dirigido bipartito hechos ↔ reglas:
      hecho ──(valor esperado)──► regla ──(confianza)──► hecho concluido
    Los hechos se clasifican como 'entrada', 'intermedio' o 'diagnostico'.
    """
    diagnosticos = {r.conclusion for r in base.reglas if r.es_diagnostico}
    nodos: list[dict] = []

    for hecho, pregunta in base.preguntas.items():
        nodos.append({"id": hecho, "tipo": "entrada", "etiqueta": pregunta})
    for hecho in dict.fromkeys(r.conclusion for r in base.reglas):
        nodos.append({
            "id": hecho,
            "tipo": "diagnostico" if hecho in diagnosticos else "intermedio",
            "etiqueta": base.reglas_que_concluyen(hecho)[0].descripcion,
        })

    aristas: list[dict] = []
    for r in base.reglas:
        nodos.append({"id": r.id, "tipo": "regla", "etiqueta": r.descripcion,
                      "confianza": r.confianza})
        for hecho, valor in r.condiciones.items():
            aristas.append({"origen": hecho, "destino": r.id, "valor": valor})
        aristas.append({"origen": r.id, "destino": r.conclusion, "confianza": r.confianza})

    return {"nombre": base.nombre, "nodos": nodos, "aristas": aristas}
