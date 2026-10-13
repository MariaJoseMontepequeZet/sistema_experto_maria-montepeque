// Funciones puras de presentación y validación (se prueban sin navegador).

import type { Pregunta, Valor } from "./tipos.js";

export const TOPE_LOGO_BYTES = 500 * 1024;

/** El texto con que se muestra una respuesta ya dada. */
export function formatearRespuesta(pregunta: Pregunta | undefined, valor: Valor): string {
  if (valor === null) return "No sé";
  if (typeof valor === "boolean") return valor ? "Sí" : "No";
  if (typeof valor === "number") {
    const numero = Number.isInteger(valor) ? String(valor) : String(Number(valor.toFixed(2)));
    return pregunta?.unidad ? `${numero} ${pregunta.unidad}` : numero;
  }
  return pregunta?.opciones.find((o) => o.valor === valor)?.etiqueta ?? valor;
}

/** Porcentaje entero para mostrar, acotado a 0–100. */
export function porcentaje(certeza: number): number {
  return Math.round(Math.max(0, Math.min(1, certeza)) * 100);
}

/** Valida el texto escrito en una pregunta numérica. Devuelve el número o un mensaje de error. */
export function leerNumero(texto: string, pregunta: Pick<Pregunta, "minimo" | "maximo" | "unidad">): number | string {
  const limpio = texto.trim().replace(",", ".");
  if (limpio === "") return "Escribe un valor.";
  const numero = Number(limpio);
  if (!Number.isFinite(numero)) return "Escribe solo un número.";
  const { minimo, maximo, unidad } = pregunta;
  const sufijo = unidad ? ` ${unidad}` : "";
  if (minimo !== null && numero < minimo) return `El valor mínimo es ${minimo}${sufijo}.`;
  if (maximo !== null && numero > maximo) return `El valor máximo es ${maximo}${sufijo}.`;
  return numero;
}

export function esColorValido(color: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(color);
}

/** Comprueba el logo elegido: PNG o JPG de hasta ~500 KB. Devuelve un mensaje si no sirve. */
export function problemaConLogo(tipo: string, bytes: number): string | null {
  if (tipo !== "image/png" && tipo !== "image/jpeg") return "El logo debe ser un PNG o un JPG.";
  if (bytes > TOPE_LOGO_BYTES) return "El logo pesa más de 500 KB. Usa una imagen más pequeña.";
  return null;
}

/** Nombre del archivo PDF a partir del equipo (sin caracteres raros). */
export function nombreDeInforme(equipo: string): string {
  const base = equipo
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase()
    .slice(0, 40);
  return base ? `informe-${base}.pdf` : "informe-diagnostico.pdf";
}
