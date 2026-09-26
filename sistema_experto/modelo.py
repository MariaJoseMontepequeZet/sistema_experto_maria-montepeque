"""
Estructuras de datos del sistema experto.

- Hecho             : un hecho de entrada (lo que se le pregunta al usuario) y su tipo de respuesta.
- Condicion         : lo que una regla exige de un hecho (sí/no, una opción o un rango numérico).
- Regla             : una unidad de conocimiento "SI condiciones ENTONCES hecho", con una
                      confianza entre -1 y 1 (negativa = evidencia en contra).
- BaseDeConocimiento: hechos de entrada + reglas.
- BaseDeHechos      : memoria de trabajo de UNA consulta (valores, certeza y origen).
"""

from __future__ import annotations

import operator
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

ORIGEN_USUARIO = "usuario"

# Tipos de respuesta de un hecho de entrada
SI_NO, OPCION, NUMERO = "si_no", "opcion", "numero"
TIPOS = (SI_NO, OPCION, NUMERO)

OPERADORES = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}
SIMBOLOS = {">": ">", ">=": "≥", "<": "<", "<=": "≤"}

# Certeza mínima para dar un hecho derivado por establecido (convención de MYCIN).
UMBRAL_CERTEZA = 0.2

# Valor de una respuesta: True/False (si_no), str (opcion), float (numero) o None (no sé)
Valor = bool | str | float | None


def es_numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def formatear_numero(numero: float) -> str:
    return f"{numero:g}"


def porcentaje(certeza: float) -> str:
    """Certeza como porcentaje. Solo una certeza exactamente 1 se muestra como 100 %:
    un diagnóstico casi seguro no debe presentarse como infalible por el redondeo."""
    valor = certeza * 100
    if abs(certeza) < 1:
        valor = max(-99.0, min(99.0, valor))
    return f"{valor:.0f}%"


def combinar_certezas(a: float, b: float) -> float:
    """
    Combina dos evidencias independientes sobre el mismo hecho (factores de certeza de MYCIN):
      ambas a favor   → a + b·(1 − a)
      ambas en contra → a + b·(1 + a)
      signos opuestos → (a + b) / (1 − min(|a|, |b|))
    El resultado siempre queda entre -1 y 1, y no depende del orden.
    """
    if a >= 0 and b >= 0:
        return a + b * (1 - a)
    if a < 0 and b < 0:
        return a + b * (1 + a)
    denominador = 1 - min(abs(a), abs(b))
    return (a + b) / denominador if denominador else 0.0


@dataclass(frozen=True)
class Hecho:
    """Hecho de entrada: la pregunta y qué respuestas admite."""
    nombre: str
    pregunta: str
    tipo: str = SI_NO
    opciones: tuple[tuple[str, str], ...] = ()   # (valor, etiqueta) para tipo 'opcion'
    unidad: str = ""                              # para tipo 'numero'
    minimo: float | None = None
    maximo: float | None = None
    ayuda: str | None = None                      # cómo averiguar la respuesta
    prueba: bool = False                          # pide una acción de verificación: se pregunta al final

    @property
    def valores_opcion(self) -> tuple[str, ...]:
        return tuple(valor for valor, _ in self.opciones)

    def admite(self, valor: Valor) -> bool:
        """¿Es `valor` una respuesta válida para este hecho? (None = "no sé" siempre vale)."""
        if valor is None:
            return True
        if self.tipo == SI_NO:
            return isinstance(valor, bool)
        if self.tipo == OPCION:
            return valor in self.valores_opcion
        return (es_numero(valor)
                and (self.minimo is None or valor >= self.minimo)
                and (self.maximo is None or valor <= self.maximo))

    def formatear(self, valor: Valor) -> str:
        if valor is None:
            return "no sé"
        if self.tipo == SI_NO:
            return "sí" if valor else "no"
        if self.tipo == OPCION:
            return dict(self.opciones).get(valor, str(valor))
        return f"{formatear_numero(valor)} {self.unidad}".strip()


@dataclass(frozen=True)
class Condicion:
    """
    Lo que una regla exige de un hecho. Se escribe en el JSON como:
      true / false            → hecho sí/no
      "laptop"                → hecho de opción igual a ese valor
      ["a", "b"]              → hecho de opción igual a cualquiera de esos valores
      {">=": 90, "<": 100}    → hecho numérico dentro del rango (todas las comparaciones)
    """
    esperado: bool | frozenset[str] | tuple[tuple[str, float], ...]
    original: Any = field(default=None, compare=False, hash=False)   # tal como vino en el JSON

    @classmethod
    def desde(cls, spec: Any) -> Condicion:
        """Construye la condición a partir de su forma en el JSON. Lanza ValueError si es inválida."""
        if isinstance(spec, Condicion):
            return spec
        if isinstance(spec, bool):
            return cls(spec, spec)
        if isinstance(spec, str) and spec:
            return cls(frozenset([spec]), spec)
        if isinstance(spec, list) and spec and all(isinstance(v, str) and v for v in spec):
            return cls(frozenset(spec), list(spec))
        if isinstance(spec, Mapping) and spec:
            desconocidos = sorted(set(spec) - set(OPERADORES))
            if desconocidos:
                raise ValueError(f"operadores desconocidos {desconocidos} "
                                 f"(permitidos: {sorted(OPERADORES)})")
            if not all(es_numero(n) for n in spec.values()):
                raise ValueError("los límites numéricos deben ser números")
            comparaciones = tuple(sorted((op, float(n)) for op, n in spec.items()))
            return cls(comparaciones, dict(spec))
        raise ValueError("debe ser true/false, un texto, una lista de textos o "
                         'un objeto de comparaciones como {">=": 90}')

    @property
    def tipo(self) -> str:
        """Tipo de hecho al que se puede aplicar esta condición."""
        if isinstance(self.esperado, bool):
            return SI_NO
        if isinstance(self.esperado, frozenset):
            return OPCION
        return NUMERO

    def cumple(self, valor: Valor) -> bool:
        if valor is None:
            return False
        if isinstance(self.esperado, bool):
            return valor is self.esperado
        if isinstance(self.esperado, frozenset):
            return valor in self.esperado
        return es_numero(valor) and all(OPERADORES[op](valor, n) for op, n in self.esperado)

    def describir(self, hecho: Hecho | None = None) -> str:
        """Texto legible: 'sí', 'no', 'Laptop', 'A o B', '≥ 90 °C'."""
        if isinstance(self.esperado, bool):
            return "sí" if self.esperado else "no"
        if isinstance(self.esperado, frozenset):
            if isinstance(self.original, str):
                valores = [self.original]
            elif isinstance(self.original, list):
                valores = self.original
            else:
                valores = sorted(self.esperado)
            etiquetas = [hecho.formatear(v) if hecho else v for v in valores]
            return " o ".join(etiquetas)
        unidad = f" {hecho.unidad}" if hecho and hecho.unidad else ""
        return " y ".join(f"{SIMBOLOS[op]} {formatear_numero(n)}{unidad}" for op, n in self.esperado)

    def a_json(self) -> Any:
        return self.original if self.original is not None else self.esperado


@dataclass(frozen=True)
class Regla:
    id: str
    descripcion: str
    condiciones: dict[str, Condicion]   # hecho -> lo que la regla exige de él
    conclusion: str                     # hecho que se afirma al disparar la regla
    confianza: float
    recomendacion: str | None = None
    advertencia: str | None = None      # aviso de seguridad que acompaña a la recomendación

    def __post_init__(self) -> None:
        # Permite escribir condiciones "en crudo" ({"x": True}) al crear reglas desde código.
        object.__setattr__(self, "condiciones",
                           {h: Condicion.desde(c) for h, c in self.condiciones.items()})

    @property
    def es_diagnostico(self) -> bool:
        """Las reglas con recomendación son diagnósticos finales; las demás derivan
        hechos intermedios o aportan evidencia a favor o en contra de un diagnóstico."""
        return self.recomendacion is not None

    @property
    def en_contra(self) -> bool:
        return self.confianza < 0

    @property
    def especificidad(self) -> int:
        return len(self.condiciones)


@dataclass(frozen=True)
class BaseDeConocimiento:
    nombre: str
    hechos: dict[str, Hecho]            # hechos de entrada, en el orden del archivo
    reglas: tuple[Regla, ...]

    @property
    def preguntas(self) -> dict[str, str]:
        """hecho de entrada -> texto de la pregunta."""
        return {nombre: h.pregunta for nombre, h in self.hechos.items()}

    def regla(self, id_regla: str) -> Regla | None:
        for r in self.reglas:
            if r.id.upper() == id_regla.upper():
                return r
        return None

    def reglas_que_concluyen(self, hecho: str) -> list[Regla]:
        return self._por_conclusion.get(hecho, [])

    @cached_property
    def _por_conclusion(self) -> dict[str, list[Regla]]:
        indice: dict[str, list[Regla]] = {}
        for r in self.reglas:
            indice.setdefault(r.conclusion, []).append(r)
        return indice

    @property
    def hechos_derivados(self) -> set[str]:
        return set(self._por_conclusion)

    @cached_property
    def hechos_diagnostico(self) -> set[str]:
        """Hechos que concluye al menos una regla con recomendación."""
        return {r.conclusion for r in self.reglas if r.es_diagnostico}

    def evidencias_de(self, hecho: str) -> list[Regla]:
        """Reglas sin recomendación que aportan evidencia (a favor o en contra) a un diagnóstico."""
        return [r for r in self.reglas_que_concluyen(hecho) if not r.es_diagnostico]

    @cached_property
    def niveles(self) -> dict[str, int]:
        """
        Nivel de cada hecho derivado: 1 + el mayor nivel de los hechos derivados de los que
        depende (los de entrada son nivel 0). El motor completa un nivel antes de pasar al
        siguiente, así toda la evidencia de un hecho se reúne antes de usarlo.
        """
        niveles: dict[str, int] = {}

        def nivel(hecho: str, camino: frozenset[str] = frozenset()) -> int:
            if hecho not in self._por_conclusion or hecho in camino:
                return 0
            if hecho not in niveles:
                niveles[hecho] = 1 + max(
                    (nivel(h, camino | {hecho}) for r in self._por_conclusion[hecho] for h in r.condiciones),
                    default=0,
                )
            return niveles[hecho]

        for hecho in self._por_conclusion:
            nivel(hecho)
        return niveles

    def formatear(self, hecho: str, valor: Valor) -> str:
        if hecho in self.hechos:
            return self.hechos[hecho].formatear(valor)
        return "sí" if valor else "no"

    def describir(self, hecho: str, condicion: Condicion) -> str:
        return condicion.describir(self.hechos.get(hecho))


@dataclass
class BaseDeHechos:
    """
    Memoria de trabajo. Un hecho está en `valores` con su valor
    (True/False, una opción o un número) o no está (desconocido).
    """
    valores: dict[str, Valor] = field(default_factory=dict)
    certeza: dict[str, float] = field(default_factory=dict)
    origen: dict[str, list[str]] = field(default_factory=dict)

    def afirmar(self, hecho: str, valor: Valor = True,
                certeza: float = 1.0, origen: str = ORIGEN_USUARIO) -> None:
        """
        Registra un hecho. Si ya tenía ese valor y llega otra evidencia a favor,
        combina las certezas con la fórmula de MYCIN: cf = cf1 + cf2 * (1 - cf1).
        """
        if hecho in self.valores and self.valores[hecho] == valor:
            previa = self.certeza[hecho]
            self.certeza[hecho] = previa + certeza * (1 - previa)
            self.origen[hecho].append(origen)
        else:
            self.valores[hecho] = valor
            self.certeza[hecho] = certeza
            self.origen[hecho] = [origen]

    def agregar_evidencia(self, hecho: str, certeza: float, origen: str) -> None:
        """
        Suma una evidencia (a favor si es positiva, en contra si es negativa) sobre un hecho
        derivado. El hecho queda establecido mientras su certeza neta supere el umbral.
        """
        if hecho in self.certeza:
            self.certeza[hecho] = combinar_certezas(self.certeza[hecho], certeza)
            self.origen[hecho].append(origen)
        else:
            self.certeza[hecho] = certeza
            self.origen[hecho] = [origen]
        if self.certeza[hecho] > UMBRAL_CERTEZA:
            self.valores[hecho] = True
        else:
            self.valores.pop(hecho, None)

    def valor(self, hecho: str) -> Valor:
        return self.valores.get(hecho)

    def cumple(self, condiciones: Mapping[str, Condicion]) -> bool:
        return all(c.cumple(self.valores.get(h)) for h, c in condiciones.items())

    def certeza_minima(self, condiciones: Mapping[str, Condicion]) -> float:
        """Certeza de una conjunción (AND): la del eslabón más débil."""
        return min((self.certeza[h] for h in condiciones), default=1.0)
