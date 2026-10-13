// Lo que se recuerda en el navegador. Todo puede fallar (modo privado, almacenamiento bloqueado):
// la app funciona igual sin esto, solo que no recuerda.

import { esColorValido } from "./formato.js";
import type { Marca, Servicio } from "./tipos.js";

const CLAVE = "diagnostico.clave";
const MARCA = "diagnostico.marca";
const SERVICIO = "diagnostico.tecnico";

export const MARCA_POR_DEFECTO: Marca = { nombre: "", color: "#1f4e79", contacto: "", logo_base64: null };

function leer(almacen: Storage, nombre: string): string | null {
  try {
    return almacen.getItem(nombre);
  } catch {
    return null;
  }
}

function escribir(almacen: Storage, nombre: string, valor: string | null): void {
  try {
    if (valor === null) almacen.removeItem(nombre);
    else almacen.setItem(nombre, valor);
  } catch {
    // sin almacenamiento: no se recuerda y ya
  }
}

/** La clave dura mientras la pestaña esté abierta; al cerrarla hay que volver a escribirla. */
export const claveGuardada = (): string => leer(sessionStorage, CLAVE) ?? "";
export const guardarClave = (clave: string | null): void => escribir(sessionStorage, CLAVE, clave);

/** La marca del taller se recuerda entre visitas, porque es siempre la misma. */
export function marcaGuardada(): Marca {
  const crudo = leer(localStorage, MARCA);
  if (!crudo) return { ...MARCA_POR_DEFECTO };
  try {
    const m = JSON.parse(crudo) as Partial<Marca>;
    return {
      nombre: typeof m.nombre === "string" ? m.nombre : "",
      color: typeof m.color === "string" && esColorValido(m.color) ? m.color : MARCA_POR_DEFECTO.color,
      contacto: typeof m.contacto === "string" ? m.contacto : "",
      logo_base64: typeof m.logo_base64 === "string" ? m.logo_base64 : null,
    };
  } catch {
    return { ...MARCA_POR_DEFECTO };
  }
}

export const guardarMarca = (marca: Marca): void => escribir(localStorage, MARCA, JSON.stringify(marca));

/** Solo el nombre del técnico se recuerda; los datos del cliente y el equipo son de cada servicio. */
export const tecnicoGuardado = (): Servicio["tecnico"] => leer(localStorage, SERVICIO) ?? "";
export const guardarTecnico = (nombre: string): void => escribir(localStorage, SERVICIO, nombre);
