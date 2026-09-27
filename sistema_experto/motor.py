"""
Motor de inferencia.

No sabe nada de computadoras ni imprime nada: recibe una base de
conocimiento y respuestas, y devuelve estructuras de datos que la
interfaz (cli.py u otra) decide cómo mostrar.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cached_property

from .modelo import (
    NUMERO,
    OPCION,
    UMBRAL_CERTEZA,
    BaseDeConocimiento,
    BaseDeHechos,
    Condicion,
    Hecho,
    Regla,
    Valor,
    combinar_certezas,
)

# hecho de entrada -> True/False (sí/no), una opción, un número, o None (no sé)
Respuestas = Mapping[str, Valor]

# Los diagnósticos a menos de esta distancia del principal compiten con él: la consulta
# prioriza la pregunta que mejor los separa (diagnóstico diferencial).
MARGEN_DIFERENCIAL = 0.2

# ──────────────────────────────────────────────────────────────
# Encadenamiento hacia adelante
# ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Disparo:
    """Registro de una regla ejecutada en un ciclo del motor."""
    ciclo: int
    regla: Regla
    certeza: float                    # confianza de la regla × certeza de sus premisas (negativa = en contra)
    conflict_set: tuple[str, ...]     # reglas candidatas en ese ciclo


@dataclass(frozen=True)
class Diagnostico:
    hecho: str
    certeza: float                    # certeza neta: todas las evidencias combinadas (MYCIN)
    disparos: tuple[Disparo, ...]     # todas las reglas que aportaron evidencia, a favor y en contra

    @property
    def descripcion(self) -> str:
        return next(d.regla.descripcion for d in self.disparos if d.regla.es_diagnostico)

    @property
    def a_favor(self) -> list[Disparo]:
        return [d for d in self.disparos if d.certeza > 0]

    @property
    def en_contra(self) -> list[Disparo]:
        return [d for d in self.disparos if d.certeza < 0]

    @property
    def establecido(self) -> bool:
        return self.certeza > UMBRAL_CERTEZA

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

    @cached_property
    def _evaluados(self) -> list[Diagnostico]:
        """Cada diagnóstico al que llegó alguna regla con recomendación, con toda su evidencia."""
        con_recomendacion = {d.regla.conclusion for d in self.disparos if d.regla.es_diagnostico}
        por_hecho: dict[str, list[Disparo]] = {}
        for d in self.disparos:
            if d.regla.conclusion in con_recomendacion:
                por_hecho.setdefault(d.regla.conclusion, []).append(d)
        evaluados = [Diagnostico(hecho, self.hechos.certeza[hecho], tuple(ds))
                     for hecho, ds in por_hecho.items()]
        return sorted(
            evaluados,
            key=lambda dg: (dg.certeza, max(d.regla.especificidad for d in dg.disparos)),
            reverse=True,
        )

    @property
    def diagnosticos(self) -> list[Diagnostico]:
        """Diagnósticos cuya certeza neta supera el umbral, de mayor a menor certeza."""
        return [dg for dg in self._evaluados if dg.establecido]

    @property
    def descartados(self) -> list[Diagnostico]:
        """Diagnósticos que una regla sugirió pero que la evidencia en contra dejó bajo el umbral."""
        return [dg for dg in self._evaluados if not dg.establecido]

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


def resolver_conflictos(conflict_set: list[Regla],
                        niveles: Mapping[str, int] | None = None) -> Regla | None:
    """
    Primero las reglas del nivel más bajo (así toda la evidencia de un hecho se reúne antes
    de usarlo en otra regla); dentro del nivel, mayor confianza absoluta y luego la regla
    más específica.
    """
    if not conflict_set:
        return None
    niveles = niveles or {}
    return min(conflict_set,
               key=lambda r: (niveles.get(r.conclusion, 0), -abs(r.confianza), -r.especificidad))


def encadenar_hacia_adelante(base: BaseDeConocimiento,
                             respuestas: Respuestas) -> Inferencia:
    """
    Ciclo reconocer-actuar hasta punto fijo:
      equiparar → resolver conflictos → disparar (sumar la evidencia a la conclusión)
    Los hechos derivados alimentan a otras reglas en ciclos posteriores. Cada disparo suma
    evidencia a favor o en contra; un hecho derivado queda establecido mientras su certeza
    neta supere el umbral. Las respuestas "no sé" (None) dejan el hecho como desconocido.
    """
    desconocidos = set(respuestas) - set(base.hechos)
    if desconocidos:
        raise ValueError(f"Hechos de entrada desconocidos: {sorted(desconocidos)}")
    for hecho, valor in respuestas.items():
        if not base.hechos[hecho].admite(valor):
            raise ValueError(f"Respuesta no válida para '{hecho}': {valor!r}")

    hechos = BaseDeHechos()
    for hecho, valor in respuestas.items():
        if valor is not None:
            hechos.afirmar(hecho, valor)

    # Las respuestas no cambian durante la inferencia: una regla que ya contradice alguna
    # nunca podrá dispararse, así que se descarta una sola vez en lugar de en cada ciclo.
    candidatas = [r for r in base.reglas
                  if all(c.cumple(hechos.valor(h)) for h, c in r.condiciones.items() if h in base.hechos)]

    inferencia = Inferencia(hechos)
    disparadas: set[str] = set()
    ciclo = 0
    while True:
        conflict_set = equiparar(candidatas, hechos, disparadas)
        regla = resolver_conflictos(conflict_set, base.niveles)
        if regla is None:
            return inferencia
        ciclo += 1
        certeza = regla.confianza * hechos.certeza_minima(regla.condiciones)
        hechos.agregar_evidencia(regla.conclusion, certeza, origen=regla.id)
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
    esperado: Condicion
    actual: Valor
    subobjetivos: tuple[AnalisisRegla, ...] = ()   # reglas que podrían derivar el hecho

    @property
    def estado(self) -> str:
        if self.actual is None:
            return PENDIENTE
        return CUMPLIDA if self.esperado.cumple(self.actual) else CONTRADICHA


@dataclass(frozen=True)
class AnalisisRegla:
    regla: Regla
    condiciones: tuple[EstadoCondicion, ...]

    # cached_property: el análisis es inmutable, así que cada resultado se calcula una sola vez
    @cached_property
    def se_activa(self) -> bool:
        return all(c.estado == CUMPLIDA for c in self.condiciones)

    @cached_property
    def descartada(self) -> bool:
        return any(c.estado == CONTRADICHA for c in self.condiciones)

    @cached_property
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
    entrada: Hecho | None = None   # tipo de respuesta, opciones, unidad y ayuda
    rivales: tuple[Diagnostico, ...] = ()   # par de diagnósticos cercanos que esta respuesta separa


def hipotesis_abiertas(base: BaseDeConocimiento, respuestas: Respuestas) -> list[AnalisisRegla]:
    """
    Diagnósticos que todavía pueden activarse y para los que queda alguna
    pregunta sin hacer. Los descartados, los ya confirmados, los que solo
    dependen de respuestas "no sé" y los que ya no pueden superar el umbral
    con la evidencia que falta quedan fuera.
    """
    return _Consulta(base, respuestas).abiertas


def siguiente_pregunta(base: BaseDeConocimiento, respuestas: Respuestas) -> Pregunta | None:
    """
    Elige la pregunta que más hipótesis abiertas necesitan (así cada respuesta
    confirma o descarta la mayor cantidad posible). Desempata por la confianza
    de las hipótesis y luego por el orden del archivo de conocimiento.

    Primero se agotan los síntomas; las pruebas de verificación (acciones que el
    usuario tiene que hacer) se proponen al final, solo para las hipótesis que
    siguen abiertas. Devuelve None cuando ya no queda nada útil por preguntar.

    Diagnóstico diferencial: si hay diagnósticos cerca del principal, entre las
    preguntas disponibles va primero la que más puede separar a dos de ellos.
    """
    consulta = _Consulta(base, respuestas)
    interesadas = consulta.interesadas
    sintomas = {h: rs for h, rs in interesadas.items() if not base.hechos[h].prueba}
    candidatas = sintomas or interesadas
    if not candidatas:
        return None

    sin_separar = (0.0, ())
    separacion = {h: consulta.separacion(h) for h in candidatas} if consulta.rivales else {}
    orden = list(base.preguntas)
    hecho = max(
        candidatas,
        key=lambda h: (separacion.get(h, sin_separar)[0],
                       len(candidatas[h]),
                       max(abs(r.confianza) for r in candidatas[h]),
                       -orden.index(h)),
    )
    return _pregunta(base, hecho, interesadas, separacion.get(hecho, sin_separar)[1])


def pregunta_sobre(base: BaseDeConocimiento, respuestas: Respuestas, hecho: str) -> Pregunta:
    """Arma la pregunta de un hecho con las hipótesis abiertas que dependen de él."""
    return _pregunta(base, hecho, _Consulta(base, respuestas).interesadas)


def _pregunta(base: BaseDeConocimiento, hecho: str, interesadas: dict[str, list[Regla]],
              rivales: tuple[Diagnostico, ...] = ()) -> Pregunta:
    hipotesis = sorted(interesadas.get(hecho, []), key=lambda r: r.confianza, reverse=True)
    entrada = base.hechos[hecho]
    return Pregunta(hecho, entrada.pregunta, tuple(hipotesis), entrada, rivales)


class _Consulta:
    """
    Lo que se deduce de unas respuestas para elegir la siguiente pregunta: el análisis
    de cada regla, la inferencia y qué diagnósticos todavía pueden establecerse. Cada
    cálculo se hace una sola vez (no cambia mientras no cambien las respuestas).
    """

    def __init__(self, base: BaseDeConocimiento, respuestas: Respuestas):
        self.base, self.respuestas = base, respuestas
        self._analisis: dict[str, AnalisisRegla] = {}

    def analizar(self, regla: Regla) -> AnalisisRegla:
        if regla.id not in self._analisis:
            self._analisis[regla.id] = _analizar(self.base, regla, self.respuestas, frozenset())
        return self._analisis[regla.id]

    def puede_dispararse(self, regla: Regla) -> bool:
        """¿Queda alguna pregunta sin hacer que podría activar la regla?
        (las respondidas con "no sé" no cuentan)."""
        return any(h not in self.respuestas for h in self.analizar(regla).por_preguntar)

    @cached_property
    def inferencia(self) -> Inferencia:
        return encadenar_hacia_adelante(self.base, self.respuestas)

    @cached_property
    def alcanzables(self) -> set[str]:
        """
        Diagnósticos que todavía pueden superar el umbral. Su cota combina la evidencia ya
        disparada con toda la evidencia a favor que las preguntas pendientes aún pueden
        activar, a la confianza máxima de cada regla, y supone que no llega más evidencia
        en contra. Como cada evidencia a favor solo puede subir la certeza (MYCIN), ninguna
        combinación de respuestas supera esa cota: si no pasa el umbral, seguir preguntando
        por ese diagnóstico ya no puede cambiar el resultado.
        """
        disparos: dict[str, list[Disparo]] = {}
        for d in self.inferencia.disparos:
            disparos.setdefault(d.regla.conclusion, []).append(d)

        alcanzables = set()
        for diagnostico in self.base.hechos_diagnostico:
            ya = disparos.get(diagnostico, [])
            disparadas = {d.regla.id for d in ya}
            pendientes = [r for r in self.base.reglas_que_concluyen(diagnostico)
                          if r.id not in disparadas and not r.en_contra and self.puede_dispararse(r)]
            # sin una regla con recomendación, disparada o todavía posible, no hay diagnóstico
            if not any(r.es_diagnostico for r in [d.regla for d in ya] + pendientes):
                continue
            # A favor se usa la confianza de la regla (la certeza de sus premisas aún puede
            # crecer); en contra, lo ya disparado (su peso solo puede crecer, nunca bajar).
            evidencias = [d.certeza if d.certeza < 0 else d.regla.confianza for d in ya]
            evidencias += [r.confianza for r in pendientes]
            cota = 0.0
            for certeza in evidencias:
                cota = combinar_certezas(cota, certeza)
            if cota > UMBRAL_CERTEZA:
                alcanzables.add(diagnostico)
        return alcanzables

    @cached_property
    def abiertas(self) -> list[AnalisisRegla]:
        return [self.analizar(r) for r in self.base.reglas
                if r.es_diagnostico and r.conclusion in self.alcanzables and self.puede_dispararse(r)]

    @cached_property
    def interesadas(self) -> dict[str, list[Regla]]:
        """Hecho sin responder -> reglas de los diagnósticos alcanzables que dependen de él."""
        interesadas: dict[str, list[Regla]] = {}
        for analisis in self.abiertas:
            for hecho in analisis.por_preguntar:
                if hecho not in self.respuestas:
                    interesadas.setdefault(hecho, []).append(analisis.regla)

        # Evidencia a favor o en contra de los diagnósticos que todavía pueden establecerse:
        # puede cambiar su certeza, así que también vale la pena preguntarla.
        for diagnostico in self.alcanzables:
            for regla in self.base.evidencias_de(diagnostico):
                for hecho in self.analizar(regla).por_preguntar:
                    if hecho not in self.respuestas:
                        interesadas.setdefault(hecho, []).append(regla)
        return interesadas

    @cached_property
    def rivales(self) -> tuple[Diagnostico, ...]:
        """Diagnósticos establecidos tan cerca del principal que conviene separarlos."""
        diagnosticos = self.inferencia.diagnosticos
        cercanos = [dg for dg in diagnosticos
                    if diagnosticos[0].certeza - dg.certeza < MARGEN_DIFERENCIAL]
        return tuple(cercanos) if len(cercanos) >= 2 else ()

    def separacion(self, hecho: str) -> tuple[float, tuple[Diagnostico, ...]]:
        """
        Cuánto puede cambiar, según lo que se responda a `hecho`, la distancia entre dos
        rivales (se simula cada respuesta posible), y qué par separa más. 0 = no distingue
        a ningún par.
        """
        simuladas = []
        for valor in _respuestas_posibles(self.base, hecho):
            inferencia = encadenar_hacia_adelante(self.base, {**self.respuestas, hecho: valor})
            simuladas.append({dg.hecho: dg.certeza for dg in inferencia._evaluados})

        mejor: tuple[float, tuple[Diagnostico, ...]] = (0.0, ())
        for a, b in itertools.combinations(self.rivales, 2):
            distancias = [c.get(a.hecho, 0.0) - c.get(b.hecho, 0.0) for c in simuladas]
            # redondeo: diferencias de coma flotante no deben decidir entre dos preguntas
            separa = round(max(distancias) - min(distancias), 6) if distancias else 0.0
            if separa > mejor[0]:
                mejor = (separa, (a, b))
        return mejor


def _respuestas_posibles(base: BaseDeConocimiento, hecho: str) -> tuple[Valor, ...]:
    """
    Una respuesta por cada caso que distinguen las reglas. Para un hecho numérico, un valor
    en cada región que delimitan los umbrales de sus condiciones.
    """
    entrada = base.hechos[hecho]
    if entrada.tipo == OPCION:
        return entrada.valores_opcion
    if entrada.tipo != NUMERO:
        return (True, False)
    umbrales = sorted({n for r in base.reglas if hecho in r.condiciones
                       for _, n in r.condiciones[hecho].esperado})
    if not umbrales:
        return ()
    valores = {umbrales[0] - 1, umbrales[-1] + 1}
    valores |= {(a + b) / 2 for a, b in itertools.pairwise(umbrales)}
    return tuple(v for v in sorted(valores) if entrada.admite(v))


def _analizar(base: BaseDeConocimiento, regla: Regla,
              respuestas: Respuestas, camino: frozenset[str]) -> AnalisisRegla:
    camino = camino | {regla.id}
    estados = []
    for hecho, esperado in regla.condiciones.items():
        derivadoras = [r for r in base.reglas_que_concluyen(hecho)
                       if r.id not in camino and not r.en_contra]
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

    for nombre, hecho in base.hechos.items():
        nodo = {"id": nombre, "tipo": "entrada", "etiqueta": hecho.pregunta, "respuesta": hecho.tipo}
        if hecho.opciones:
            nodo["opciones"] = dict(hecho.opciones)
        if hecho.unidad:
            nodo["unidad"] = hecho.unidad
        if hecho.prueba:
            nodo["prueba"] = True
        nodos.append(nodo)
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
        for hecho, condicion in r.condiciones.items():
            aristas.append({"origen": hecho, "destino": r.id, "valor": condicion.a_json()})
        aristas.append({"origen": r.id, "destino": r.conclusion, "confianza": r.confianza})

    return {"nombre": base.nombre, "nodos": nodos, "aristas": aristas}
