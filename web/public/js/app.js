// El flujo de la aplicación: guarda el estado, llama a la API y vuelve a pintar.
import * as api from "./api.js";
import { claveGuardada, guardarClave } from "./almacen.js";
import { nombreDeInforme } from "./formato.js";
import { cabecera, vistaAcceso, vistaConsulta, vistaResultado } from "./vistas.js";
const estado = {
    entrado: false,
    respuestas: new Map(),
    preguntas: new Map(),
    siguiente: null,
    resultado: null,
    uso: null,
    ocupado: false,
    error: null,
};
let omitirPruebas = false;
let raiz;
let vistaAnterior = "";
function pintar() {
    const vista = !estado.entrado ? vistaAcceso : estado.resultado ? vistaResultado : vistaConsulta;
    raiz.replaceChildren(cabecera(estado, acciones), vista(estado, acciones));
    // al cambiar de pantalla o de pregunta, el foco va al título (lectores de pantalla y teclado)
    const ahora = !estado.entrado ? "acceso" : estado.resultado ? "resultado" : (estado.siguiente?.pregunta?.hecho ?? "");
    if (ahora !== vistaAnterior) {
        vistaAnterior = ahora;
        raiz.querySelector("h1")?.focus({ preventScroll: true });
        window.scrollTo({ top: 0 });
    }
}
function mostrarError(e) {
    if (e instanceof api.ErrorApi && e.estado === 401 && estado.entrado) {
        // la clave dejó de valer (revocada, cuenta suspendida): se vuelve a la entrada
        cerrarSesion();
        estado.error = e.message;
        return;
    }
    estado.error = e instanceof Error ? e.message : "Ocurrió un error inesperado.";
}
function cerrarSesion() {
    api.fijarClave("");
    guardarClave(null);
    estado.entrado = false;
    limpiarConsulta();
    estado.uso = null;
}
function limpiarConsulta() {
    estado.respuestas.clear();
    estado.preguntas.clear();
    estado.siguiente = null;
    estado.resultado = null;
    omitirPruebas = false;
}
/** Pide la próxima pregunta (o el resultado). Devuelve false si falló. */
async function avanzar() {
    estado.ocupado = true;
    estado.error = null;
    pintar();
    try {
        const respuestas = Object.fromEntries(estado.respuestas);
        const paso = await api.siguiente(respuestas, omitirPruebas);
        if (paso.terminada || !paso.pregunta) {
            estado.resultado = await api.resultado(respuestas);
            estado.siguiente = null;
            void actualizarUso();
        }
        else {
            estado.resultado = null;
            estado.preguntas.set(paso.pregunta.hecho, paso.pregunta);
            estado.siguiente = {
                pregunta: paso.pregunta,
                respondidas: paso.progreso.respondidas,
                abiertas: paso.progreso.hipotesis_abiertas,
                total: paso.progreso.diagnosticos_posibles,
            };
        }
        return true;
    }
    catch (e) {
        mostrarError(e);
        return false;
    }
    finally {
        estado.ocupado = false;
        pintar();
    }
}
async function actualizarUso() {
    try {
        estado.uso = await api.uso();
    }
    catch {
        estado.uso = null; // el contador es un extra: si falla, la consulta sigue
    }
    pintar();
}
const acciones = {
    async entrar(clave) {
        estado.ocupado = true;
        estado.error = null;
        pintar();
        api.fijarClave(clave);
        try {
            await api.validarClave();
        }
        catch (e) {
            api.fijarClave("");
            estado.error = e instanceof Error ? e.message : "No se pudo comprobar la clave.";
            estado.ocupado = false;
            pintar();
            return;
        }
        guardarClave(clave);
        estado.entrado = true;
        void actualizarUso();
        await avanzar();
    },
    salir() {
        cerrarSesion();
        estado.error = null;
        pintar();
    },
    async responder(hecho, valor) {
        const antes = new Map(estado.respuestas);
        estado.respuestas.set(hecho, valor);
        if (!(await avanzar())) {
            // si no se pudo pedir lo siguiente, la respuesta no cuenta: se sigue en la misma pregunta
            estado.respuestas = antes;
            pintar();
        }
    },
    async deshacer() {
        const ultima = [...estado.respuestas.keys()].pop();
        if (ultima === undefined)
            return;
        estado.respuestas.delete(ultima);
        omitirPruebas = false;
        estado.resultado = null;
        await avanzar();
    },
    async reiniciar() {
        limpiarConsulta();
        await avanzar();
    },
    async omitirPruebas() {
        omitirPruebas = true;
        if (!(await avanzar()))
            omitirPruebas = false;
    },
    async descargarInforme(marca, servicio) {
        const pdf = await api.informe(Object.fromEntries(estado.respuestas), marca, servicio);
        const url = URL.createObjectURL(pdf);
        const enlace = document.createElement("a");
        enlace.href = url;
        enlace.download = nombreDeInforme(servicio.equipo);
        document.body.append(enlace);
        enlace.click();
        enlace.remove();
        setTimeout(() => URL.revokeObjectURL(url), 10_000);
        void actualizarUso();
    },
};
export function arrancar(elemento) {
    raiz = elemento;
    const guardada = claveGuardada();
    if (guardada) {
        // hay una clave de esta pestaña: se prueba directamente
        void acciones.entrar(guardada);
    }
    else {
        pintar();
    }
}
