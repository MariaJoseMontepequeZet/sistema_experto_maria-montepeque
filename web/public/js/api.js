// Cliente de la API REST. La clave del taller viaja en la cabecera X-API-Key.
export class ErrorApi extends Error {
    estado;
    esperar;
    constructor(mensaje, estado, esperar) {
        super(mensaje);
        this.estado = estado;
        this.esperar = esperar;
        this.name = "ErrorApi";
    }
}
const MENSAJES = {
    401: "La clave no es válida. Revísala o pídele una nueva a quien administra tu cuenta.",
    402: "Se agotaron las consultas de tu plan este mes.",
    403: "Tu cuenta está suspendida. Contacta a soporte.",
    429: "Demasiadas llamadas seguidas. Espera un momento e inténtalo de nuevo.",
};
let clave = "";
export function fijarClave(nueva) {
    clave = nueva;
}
/** Convierte el `detail` de un error de la API (texto o lista) en una frase. */
export function textoDeDetalle(detalle) {
    if (typeof detalle === "string")
        return detalle;
    if (Array.isArray(detalle)) {
        return detalle
            .map((d) => (typeof d === "string" ? d : (d?.msg ?? "")))
            .filter(Boolean)
            .join(" ");
    }
    return "";
}
async function errorDe(r) {
    let detalle = "";
    try {
        detalle = textoDeDetalle((await r.json()).detail);
    }
    catch {
        // la respuesta no era JSON: se usa el mensaje por defecto
    }
    const esperar = Number(r.headers.get("Retry-After")) || undefined;
    let mensaje = detalle || MENSAJES[r.status] || `El servidor respondió con un error (${r.status}).`;
    if (r.status === 429 && esperar)
        mensaje = `Demasiadas llamadas seguidas. Espera ${esperar} s e inténtalo de nuevo.`;
    return new ErrorApi(mensaje, r.status, esperar);
}
async function pedir(ruta, cuerpo) {
    const cabeceras = { "X-API-Key": clave };
    const init = { headers: cabeceras };
    if (cuerpo !== undefined) {
        init.method = "POST";
        init.body = JSON.stringify(cuerpo);
        cabeceras["Content-Type"] = "application/json";
    }
    let r;
    try {
        r = await fetch(ruta, init);
    }
    catch {
        throw new ErrorApi("No se pudo conectar con el servidor. Revisa tu conexión.", 0);
    }
    if (!r.ok)
        throw await errorDe(r);
    return r;
}
/** Comprueba que la clave sirva (cualquier ruta autenticada vale). */
export async function validarClave() {
    await pedir("/v1/conocimiento");
}
/** El plan y el consumo del mes; null si el servidor no está en modo comercial. */
export async function uso() {
    try {
        return (await (await pedir("/v1/uso")).json());
    }
    catch (e) {
        if (e instanceof ErrorApi && e.estado === 404)
            return null;
        throw e;
    }
}
export async function siguiente(respuestas, omitirPruebas) {
    return (await (await pedir("/v1/consulta/siguiente", { respuestas, omitir_pruebas: omitirPruebas })).json());
}
export async function resultado(respuestas) {
    return (await (await pedir("/v1/consulta/resultado", { respuestas })).json());
}
export async function informe(respuestas, marca, servicio) {
    return (await pedir("/v1/consulta/informe", { respuestas, marca, servicio })).blob();
}
