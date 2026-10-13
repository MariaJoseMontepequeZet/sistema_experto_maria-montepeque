// Pruebas de la lógica pura de la interfaz (se ejecutan sobre el JS compilado: `npm test`).
import assert from "node:assert/strict";
import { test } from "node:test";

import { textoDeDetalle } from "../public/js/api.js";
import {
  esColorValido,
  formatearRespuesta,
  leerNumero,
  nombreDeInforme,
  porcentaje,
  problemaConLogo,
} from "../public/js/formato.js";

const opcion = { opciones: [{ valor: "laptop", etiqueta: "Laptop" }], unidad: null };
const temperatura = { opciones: [], unidad: "°C", minimo: 0, maximo: 120 };

test("formatearRespuesta muestra cada tipo de respuesta", () => {
  assert.equal(formatearRespuesta(undefined, null), "No sé");
  assert.equal(formatearRespuesta(undefined, true), "Sí");
  assert.equal(formatearRespuesta(undefined, false), "No");
  assert.equal(formatearRespuesta(opcion, "laptop"), "Laptop");
  assert.equal(formatearRespuesta(opcion, "otra"), "otra");
  assert.equal(formatearRespuesta(temperatura, 85), "85 °C");
  assert.equal(formatearRespuesta(temperatura, 85.456), "85.46 °C");
});

test("un número no se confunde con un sí", () => {
  assert.equal(formatearRespuesta(undefined, 1), "1");
  assert.equal(formatearRespuesta(undefined, 0), "0");
});

test("porcentaje redondea y acota", () => {
  assert.equal(porcentaje(0.925), 93);
  assert.equal(porcentaje(1.4), 100);
  assert.equal(porcentaje(-0.3), 0);
});

test("leerNumero acepta coma decimal y valida el rango", () => {
  assert.equal(leerNumero("85", temperatura), 85);
  assert.equal(leerNumero(" 72,5 ", temperatura), 72.5);
  assert.equal(leerNumero("0", temperatura), 0);
  assert.match(leerNumero("", temperatura), /Escribe un valor/);
  assert.match(leerNumero("abc", temperatura), /solo un número/);
  assert.match(leerNumero("-5", temperatura), /mínimo es 0 °C/);
  assert.match(leerNumero("200", temperatura), /máximo es 120 °C/);
  assert.equal(leerNumero("1e400", temperatura).constructor, String);   // Infinity no es un valor
});

test("esColorValido pide #rrggbb", () => {
  assert.ok(esColorValido("#1f4e79"));
  assert.ok(esColorValido("#AABBCC"));
  assert.ok(!esColorValido("1f4e79"));
  assert.ok(!esColorValido("#fff"));
  assert.ok(!esColorValido("rojo"));
});

test("problemaConLogo acepta PNG y JPG pequeños", () => {
  assert.equal(problemaConLogo("image/png", 1000), null);
  assert.equal(problemaConLogo("image/jpeg", 500 * 1024), null);
  assert.match(problemaConLogo("image/gif", 10), /PNG o un JPG/);
  assert.match(problemaConLogo("image/png", 500 * 1024 + 1), /500 KB/);
});

test("nombreDeInforme limpia el nombre del equipo", () => {
  assert.equal(nombreDeInforme("Laptop HP 15, serie 8CG123"), "informe-laptop-hp-15-serie-8cg123.pdf");
  assert.equal(nombreDeInforme("Computadora de María"), "informe-computadora-de-maria.pdf");
  assert.equal(nombreDeInforme("   "), "informe-diagnostico.pdf");
  assert.equal(nombreDeInforme("../../etc/passwd"), "informe-etc-passwd.pdf");
});

test("textoDeDetalle entiende los errores de la API", () => {
  assert.equal(textoDeDetalle("Cuota agotada."), "Cuota agotada.");
  assert.equal(textoDeDetalle(["'x' no es un hecho.", "otro error"]), "'x' no es un hecho. otro error");
  assert.equal(textoDeDetalle([{ msg: "color inválido" }]), "color inválido");
  assert.equal(textoDeDetalle(undefined), "");
  assert.equal(textoDeDetalle(null), "");
});
