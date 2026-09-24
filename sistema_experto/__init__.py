"""Sistema experto basado en reglas con encadenamiento hacia adelante y hacia atrás."""

from .conocimiento import ErrorDeConocimiento, cargar
from .motor import encadenar_hacia_adelante, encadenar_hacia_atras, exportar_red

__all__ = [
    "ErrorDeConocimiento",
    "cargar",
    "encadenar_hacia_adelante",
    "encadenar_hacia_atras",
    "exportar_red",
]
