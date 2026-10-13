// Cliente de la API REST. La clave del taller viaja en la cabecera X-API-Key.

import type { Marca, Resultado, Respuestas, Servicio, Siguiente, Uso } from "./tipos.js";

export class ErrorApi extends Error {
  constructor(
    mensaje: string,
    readonly estado: number,
    readonly esperar?: number,
  ) {
    super(mensaje);
    this.name = "ErrorApi";
  }
}

const MENSAJES: Record<number, string> = {
  401: "La clave no es válida. Revísala o pídele una nueva a quien administra tu cuenta.",
  402: "Se agotaron las consultas de tu plan este mes.",
  403: "Tu cuenta está suspendida. Contacta a soporte.",
  429: "Demasiadas llamadas seguidas. Espera un momento e inténtalo de nuevo.",
};

let clave = "";

export function fijarClave(nueva: string): void {
  clave = nueva;
}

/** Convierte el `detail` de un error de la API (texto o lista) en una frase. */
export function textoDeDetalle(detalle: unknown): string {
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle)) {
    return detalle
      .map((d) => (typeof d === "string" ? d : ((d as { msg?: string } | null)?.msg ?? "")))
      .filter(Boolean)
      .join(" ");
  }
  return "";
}

async function errorDe(r: Response): Promise<ErrorApi> {
  let detalle = "";
  try {
    detalle = textoDeDetalle(((await r.json()) as { detail?: unknown }).detail);
  } catch {
    // la respuesta no era JSON: se usa el mensaje por defecto
  }
  const esperar = Number(r.headers.get("Retry-After")) || undefined;
  let mensaje = detalle || MENSAJES[r.status] || `El servidor respondió con un error (${r.status}).`;
  if (r.status === 429 && esperar) mensaje = `Demasiadas llamadas seguidas. Espera ${esperar} s e inténtalo de nuevo.`;
  return new ErrorApi(mensaje, r.status, esperar);
}

async function pedir(ruta: string, cuerpo?: unknown): Promise<Response> {
  const cabeceras: Record<string, string> = { "X-API-Key": clave };
  const init: RequestInit = { headers: cabeceras };
  if (cuerpo !== undefined) {
    init.method = "POST";
    init.body = JSON.stringify(cuerpo);
    cabeceras["Content-Type"] = "application/json";
  }
  let r: Response;
  try {
    r = await fetch(ruta, init);
  } catch {
    throw new ErrorApi("No se pudo conectar con el servidor. Revisa tu conexión.", 0);
  }
  if (!r.ok) throw await errorDe(r);
  return r;
}

/** Comprueba que la clave sirva (cualquier ruta autenticada vale). */
export async function validarClave(): Promise<void> {
  await pedir("/v1/conocimiento");
}

/** El plan y el consumo del mes; null si el servidor no está en modo comercial. */
export async function uso(): Promise<Uso | null> {
  try {
    return (await (await pedir("/v1/uso")).json()) as Uso;
  } catch (e) {
    if (e instanceof ErrorApi && e.estado === 404) return null;
    throw e;
  }
}

export async function siguiente(respuestas: Respuestas, omitirPruebas: boolean): Promise<Siguiente> {
  return (await (await pedir("/v1/consulta/siguiente", { respuestas, omitir_pruebas: omitirPruebas })).json()) as Siguiente;
}

export async function resultado(respuestas: Respuestas): Promise<Resultado> {
  return (await (await pedir("/v1/consulta/resultado", { respuestas })).json()) as Resultado;
}

export async function informe(respuestas: Respuestas, marca: Marca, servicio: Servicio): Promise<Blob> {
  return (await pedir("/v1/consulta/informe", { respuestas, marca, servicio })).blob();
}
