// Lo que se recuerda en el navegador. Todo puede fallar (modo privado, almacenamiento bloqueado):
// la app funciona igual sin esto, solo que no recuerda.
import { esColorValido } from "./formato.js";
const CLAVE = "diagnostico.clave";
const MARCA = "diagnostico.marca";
const SERVICIO = "diagnostico.tecnico";
export const MARCA_POR_DEFECTO = { nombre: "", color: "#1f4e79", contacto: "", logo_base64: null };
function leer(almacen, nombre) {
    try {
        return almacen.getItem(nombre);
    }
    catch {
        return null;
    }
}
function escribir(almacen, nombre, valor) {
    try {
        if (valor === null)
            almacen.removeItem(nombre);
        else
            almacen.setItem(nombre, valor);
    }
    catch {
        // sin almacenamiento: no se recuerda y ya
    }
}
/** La clave dura mientras la pestaña esté abierta; al cerrarla hay que volver a escribirla. */
export const claveGuardada = () => leer(sessionStorage, CLAVE) ?? "";
export const guardarClave = (clave) => escribir(sessionStorage, CLAVE, clave);
/** La marca del taller se recuerda entre visitas, porque es siempre la misma. */
export function marcaGuardada() {
    const crudo = leer(localStorage, MARCA);
    if (!crudo)
        return { ...MARCA_POR_DEFECTO };
    try {
        const m = JSON.parse(crudo);
        return {
            nombre: typeof m.nombre === "string" ? m.nombre : "",
            color: typeof m.color === "string" && esColorValido(m.color) ? m.color : MARCA_POR_DEFECTO.color,
            contacto: typeof m.contacto === "string" ? m.contacto : "",
            logo_base64: typeof m.logo_base64 === "string" ? m.logo_base64 : null,
        };
    }
    catch {
        return { ...MARCA_POR_DEFECTO };
    }
}
export const guardarMarca = (marca) => escribir(localStorage, MARCA, JSON.stringify(marca));
/** Solo el nombre del técnico se recuerda; los datos del cliente y el equipo son de cada servicio. */
export const tecnicoGuardado = () => leer(localStorage, SERVICIO) ?? "";
export const guardarTecnico = (nombre) => escribir(localStorage, SERVICIO, nombre);
