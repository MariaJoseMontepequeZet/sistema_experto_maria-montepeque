// Formas de los datos que devuelve la API (ver docs/api.md).

export type Valor = boolean | number | string | null; // null = "no sé"
export type Respuestas = Record<string, Valor>;
export type TipoPregunta = "si_no" | "opcion" | "numero";

export interface Opcion {
  valor: string;
  etiqueta: string;
}

export interface Hipotesis {
  regla: string;
  descripcion: string;
  es_diagnostico: boolean;
  confianza: number;
  en_contra: boolean;
  conclusion: string;
}

export interface Rival {
  hecho: string;
  descripcion: string;
  certeza: number;
}

export interface Pregunta {
  hecho: string;
  texto: string;
  tipo: TipoPregunta;
  opciones: Opcion[];
  unidad: string | null;
  minimo: number | null;
  maximo: number | null;
  ayuda: string | null;
  prueba: boolean;
  hipotesis: Hipotesis[];
  rivales: Rival[];
}

export interface Progreso {
  respondidas: number;
  hipotesis_abiertas: number;
  diagnosticos_posibles: number;
}

export interface Siguiente {
  terminada: boolean;
  pregunta: Pregunta | null;
  progreso: Progreso;
}

export interface Evidencia {
  regla: string;
  descripcion: string;
  certeza: number;
}

export interface Paso {
  ciclo: number;
  regla: string;
  descripcion: string;
  si: string[];
  entonces: string;
  certeza: number;
}

export interface Diagnostico {
  hecho: string;
  descripcion: string;
  certeza: number;
  certeza_texto: string;
  recomendaciones: string[];
  advertencias: string[];
  evidencias: Evidencia[];
  razonamiento: Paso[];
}

export interface Descartado {
  hecho: string;
  descripcion: string;
  motivos: string[];
}

export interface Resultado {
  respondidas: number;
  diagnosticos: Diagnostico[];
  descartados: Descartado[];
  aviso: string;
}

export interface Uso {
  cliente: string;
  plan: string;
  nombre_plan: string | null;
  periodo: string;
  consultas: number;
  incluidas: number | null;
  restantes: number | null;
  limite_por_minuto: number | null;
  importe_usd: number | null;
}

/** Lo que el taller escribe para personalizar el informe PDF. */
export interface Marca {
  nombre: string;
  color: string;
  contacto: string;
  logo_base64: string | null;
}

export interface Servicio {
  cliente: string;
  equipo: string;
  tecnico: string;
  observaciones: string;
}
