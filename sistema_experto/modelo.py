"""
Estructuras de datos del sistema experto.

- Regla            : una unidad de conocimiento "SI condiciones ENTONCES hecho".
- BaseDeConocimiento: reglas + hechos de entrada (los que se le preguntan al usuario).
- BaseDeHechos     : memoria de trabajo de UNA consulta (valores, certeza y origen).
"""

from __future__ import annotations

from dataclasses import dataclass, field

ORIGEN_USUARIO = "usuario"


@dataclass(frozen=True)
class Regla:
    id: str
    descripcion: str
    condiciones: dict[str, bool]   # hecho -> valor esperado (True / False = negación)
    conclusion: str                # hecho que se afirma al disparar la regla
    confianza: float
    recomendacion: str | None = None

    @property
    def es_diagnostico(self) -> bool:
        """Las reglas con recomendación son diagnósticos finales;
        las demás solo derivan hechos intermedios."""
        return self.recomendacion is not None

    @property
    def especificidad(self) -> int:
        return len(self.condiciones)


@dataclass(frozen=True)
class BaseDeConocimiento:
    nombre: str
    preguntas: dict[str, str]      # hecho de entrada -> pregunta para el usuario
    reglas: tuple[Regla, ...]

    def regla(self, id_regla: str) -> Regla | None:
        for r in self.reglas:
            if r.id.upper() == id_regla.upper():
                return r
        return None

    def reglas_que_concluyen(self, hecho: str) -> list[Regla]:
        return [r for r in self.reglas if r.conclusion == hecho]

    @property
    def hechos_derivados(self) -> set[str]:
        return {r.conclusion for r in self.reglas}


@dataclass
class BaseDeHechos:
    """
    Memoria de trabajo. Un hecho puede estar en tres estados:
    verdadero, falso o desconocido (no presente en `valores`).
    """
    valores: dict[str, bool] = field(default_factory=dict)
    certeza: dict[str, float] = field(default_factory=dict)
    origen: dict[str, list[str]] = field(default_factory=dict)

    def afirmar(self, hecho: str, valor: bool = True,
                certeza: float = 1.0, origen: str = ORIGEN_USUARIO) -> None:
        """
        Registra un hecho. Si ya era verdadero y llega otra evidencia a favor,
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

    def valor(self, hecho: str) -> bool | None:
        return self.valores.get(hecho)

    def cumple(self, condiciones: dict[str, bool]) -> bool:
        return all(self.valores.get(h) == v for h, v in condiciones.items())

    def certeza_minima(self, condiciones: dict[str, bool]) -> float:
        """Certeza de una conjunción (AND): la del eslabón más débil."""
        return min((self.certeza[h] for h in condiciones), default=1.0)
