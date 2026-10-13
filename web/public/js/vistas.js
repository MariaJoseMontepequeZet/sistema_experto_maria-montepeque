// Las pantallas. Cada función construye el DOM a partir del estado y avisa de lo que hace el usuario
// mediante `Acciones`; no guarda estado propio (salvo el formulario del informe, que vive en el DOM).
import { guardarMarca, guardarTecnico, marcaGuardada, tecnicoGuardado } from "./almacen.js";
import { h } from "./dom.js";
import { esColorValido, formatearRespuesta, leerNumero, porcentaje, problemaConLogo, } from "./formato.js";
// ── Piezas comunes ────────────────────────────────────────────
export function cabecera(estado, acciones) {
    return h("header", { class: "cabecera" }, h("div", { class: "marca-app" }, h("span", { class: "logo", "aria-hidden": "true" }, "🖥️"), h("strong", {}, "Diagnóstico de PC")), estado.entrado
        ? h("div", { class: "cuenta" }, estado.uso && chipDeUso(estado.uso), h("button", { class: "boton texto", type: "button", onclick: () => acciones.salir() }, "Salir"))
        : null);
}
function chipDeUso(uso) {
    const texto = uso.incluidas !== null
        ? `Consultas del mes: ${uso.consultas} de ${uso.incluidas}`
        : `Consultas del mes: ${uso.consultas}`;
    const poco = uso.restantes !== null && uso.restantes <= 5;
    return h("span", { class: poco ? "chip aviso" : "chip", title: uso.nombre_plan ?? "" }, texto);
}
export function bannerDeError(mensaje) {
    return h("div", { class: "error", role: "alert", "aria-live": "assertive", hidden: mensaje === null }, mensaje ?? "");
}
function pie() {
    return h("p", { class: "pie" }, "⚠️ Este sistema orienta, no reemplaza a un técnico. Apaga y desconecta el equipo antes de abrirlo.");
}
// ── Acceso ────────────────────────────────────────────────────
export function vistaAcceso(estado, acciones) {
    const campo = h("input", {
        id: "clave",
        type: "password",
        autocomplete: "off",
        spellcheck: "false",
        placeholder: "se_...",
        required: true,
    });
    const enviar = (e) => {
        e.preventDefault();
        if (campo.value.trim())
            acciones.entrar(campo.value.trim());
    };
    return h("main", { class: "tarjeta estrecha" }, h("h1", { tabindex: "-1" }, "Entrar"), h("p", { class: "ayuda" }, "Escribe la clave de tu taller para empezar. Te la dio quien administra tu cuenta."), bannerDeError(estado.error), h("form", { onsubmit: enviar }, h("label", { for: "clave" }, "Clave de acceso"), campo, h("button", { class: "boton principal", type: "submit", disabled: estado.ocupado }, estado.ocupado ? "Comprobando…" : "Entrar")), pie());
}
// ── Consulta ──────────────────────────────────────────────────
export function vistaConsulta(estado, acciones) {
    const pregunta = estado.siguiente?.pregunta;
    if (!pregunta || !estado.siguiente)
        return h("main", { class: "tarjeta" }, h("p", {}, "Cargando…"));
    const { respondidas, abiertas, total } = estado.siguiente;
    return h("main", { class: "consulta" }, h("section", { class: "tarjeta", "aria-labelledby": "titulo-pregunta" }, h("div", { class: "progreso" }, h("span", {}, `Pregunta ${respondidas + 1}`), h("span", { class: "suave" }, `Posibles fallas aún abiertas: ${abiertas} de ${total}`)), pregunta.prueba &&
        h("p", { class: "etiqueta prueba" }, "🔧 Prueba de verificación · confirma o descarta la falla antes de reparar"), pregunta.rivales.length > 0 &&
        h("p", { class: "etiqueta rival" }, "⚖️ Diagnóstico diferencial · ¿", pregunta.rivales.map((r) => `${r.descripcion} (${porcentaje(r.certeza)} %)`).join(" o "), "? Esta respuesta ayuda a distinguirlos."), h("h1", { id: "titulo-pregunta", tabindex: "-1" }, pregunta.texto), pregunta.ayuda && h("p", { class: "ayuda" }, "💡 ", pregunta.ayuda), bannerDeError(estado.error), entradaDe(pregunta, estado.ocupado, acciones), pregunta.prueba &&
        h("button", { class: "boton texto", type: "button", disabled: estado.ocupado, onclick: () => acciones.omitirPruebas() }, "⏭️ Ver el diagnóstico sin más pruebas"), porQue(pregunta)), panelDeRespuestas(estado, acciones));
}
function entradaDe(pregunta, ocupado, acciones) {
    const noSe = h("button", { class: "boton", type: "button", disabled: ocupado, onclick: () => acciones.responder(pregunta.hecho, null) }, pregunta.prueba ? "No puedo hacerla" : "No sé");
    const boton = (texto, valor, principal = false) => h("button", {
        class: principal ? "boton principal" : "boton",
        type: "button",
        disabled: ocupado,
        onclick: () => acciones.responder(pregunta.hecho, valor),
    }, texto);
    if (pregunta.tipo === "opcion") {
        return h("div", { class: "respuestas columna" }, ...pregunta.opciones.map((o) => boton(o.etiqueta, o.valor)), noSe);
    }
    if (pregunta.tipo === "numero")
        return entradaNumerica(pregunta, ocupado, noSe, acciones);
    return h("div", { class: "respuestas" }, boton("Sí", true, true), boton("No", false), noSe);
}
function entradaNumerica(pregunta, ocupado, noSe, acciones) {
    const campo = h("input", {
        id: "numero",
        type: "text",
        inputmode: "decimal",
        autocomplete: "off",
        placeholder: "Escribe el valor",
        "aria-describedby": "error-numero",
    });
    const mensaje = h("p", { id: "error-numero", class: "error-campo", role: "alert" });
    const enviar = (e) => {
        e?.preventDefault();
        const leido = leerNumero(campo.value, pregunta);
        if (typeof leido === "string") {
            mensaje.textContent = leido;
            campo.setAttribute("aria-invalid", "true");
            campo.focus();
            return;
        }
        acciones.responder(pregunta.hecho, leido);
    };
    return h("form", { class: "numerica", onsubmit: enviar, novalidate: true }, h("label", { for: "numero" }, pregunta.unidad ? `Valor en ${pregunta.unidad}` : "Valor"), h("div", { class: "fila" }, campo, pregunta.unidad && h("span", { class: "unidad" }, pregunta.unidad)), mensaje, h("div", { class: "respuestas" }, h("button", { class: "boton principal", type: "submit", disabled: ocupado }, "Responder"), noSe));
}
function porQue(pregunta) {
    return h("details", { class: "porque" }, h("summary", {}, "🤔 ¿Por qué me preguntas esto?"), pregunta.hipotesis.length === 0
        ? h("p", {}, "Esta respuesta no cambia ninguna de las fallas que siguen abiertas.")
        : h("div", {}, h("p", {}, "Tu respuesta ayuda a confirmar o descartar:"), h("ul", {}, ...pregunta.hipotesis.map((r) => h("li", {}, h("strong", {}, r.descripcion), r.es_diagnostico
            ? ` (confianza ${porcentaje(r.confianza)} %)`
            : ` (evidencia ${r.en_contra ? "en contra" : "a favor"} de otra falla)`)))));
}
function panelDeRespuestas(estado, acciones) {
    const hay = estado.respuestas.size > 0;
    return h("aside", { class: "tarjeta lateral", "aria-label": "Tus respuestas" }, h("h2", {}, "Tus respuestas"), hay
        ? h("ol", { class: "historial" }, ...[...estado.respuestas].map(([hecho, valor]) => h("li", {}, h("span", { class: "suave" }, estado.preguntas.get(hecho)?.texto ?? hecho), h("strong", {}, formatearRespuesta(estado.preguntas.get(hecho), valor)))))
        : h("p", { class: "suave" }, "Todavía no has respondido nada."), h("div", { class: "respuestas" }, h("button", { class: "boton", type: "button", disabled: !hay || estado.ocupado, onclick: () => acciones.deshacer() }, "↩️ Deshacer"), h("button", { class: "boton", type: "button", disabled: !hay || estado.ocupado, onclick: () => acciones.reiniciar() }, "🔄 Reiniciar")));
}
// ── Resultado ─────────────────────────────────────────────────
export function vistaResultado(estado, acciones) {
    const resultado = estado.resultado;
    if (!resultado)
        return h("main", { class: "tarjeta" }, h("p", {}, "Cargando…"));
    const [principal, ...otros] = resultado.diagnosticos;
    return h("main", { class: "resultado" }, h("section", { class: "tarjeta", "aria-labelledby": "titulo-resultado" }, h("p", { class: "suave" }, `Consulta terminada con ${resultado.respondidas} respuestas.`), principal
        ? h("div", {}, h("h1", { id: "titulo-resultado", tabindex: "-1" }, principal.descripcion), barraDeCerteza(principal.certeza), ...principal.recomendaciones.map((r) => h("p", { class: "recomendacion" }, "👉 ", r)), ...principal.advertencias.map((a) => h("p", { class: "advertencia", role: "note" }, "⚠️ ", a)), razonamiento(principal))
        : h("div", {}, h("h1", { id: "titulo-resultado", tabindex: "-1" }, "Sin un diagnóstico claro"), h("p", {}, "Con estas respuestas no se llegó a ninguna falla con suficiente certeza. Se recomienda una revisión presencial.")), bannerDeError(estado.error), otros.length > 0 && h("h2", {}, "Otras fallas posibles"), ...otros.map((dg) => h("div", { class: "otro" }, h("div", { class: "fila-espaciada" }, h("strong", {}, dg.descripcion), h("span", {}, `${porcentaje(dg.certeza)} %`)), barraDeCerteza(dg.certeza, true), ...dg.recomendaciones.map((r) => h("p", { class: "suave" }, "👉 ", r)), ...dg.advertencias.map((a) => h("p", { class: "suave" }, "⚠️ ", a)))), resultado.descartados.length > 0 &&
        h("details", { class: "porque" }, h("summary", {}, "Descartadas por evidencia en contra"), h("ul", {}, ...resultado.descartados.map((d) => h("li", {}, h("strong", {}, d.descripcion), `: ${d.motivos.join("; ")}.`)))), h("div", { class: "respuestas" }, h("button", { class: "boton", type: "button", onclick: () => acciones.deshacer() }, "↩️ Corregir la última respuesta"), h("button", { class: "boton principal", type: "button", onclick: () => acciones.reiniciar() }, "🔄 Nueva consulta"))), formularioDeInforme(acciones), h("p", { class: "pie" }, "⚠️ ", resultado.aviso));
}
function barraDeCerteza(certeza, fina = false) {
    const pct = porcentaje(certeza);
    return h("div", { class: fina ? "barra fina" : "barra", role: "img", "aria-label": `Certeza ${pct} por ciento` }, h("div", { class: "relleno", style: `width:${pct}%` }), !fina && h("span", { class: "valor" }, `Certeza ${pct} %`));
}
function razonamiento(dg) {
    return h("details", { class: "porque" }, h("summary", {}, "🔗 ¿Por qué el sistema llegó a esto?"), h("ol", { class: "pasos" }, ...dg.razonamiento.map((p) => h("li", {}, h("strong", {}, `${p.regla} · ${p.descripcion}`), ` (${porcentaje(p.certeza)} %)`, h("br"), h("span", { class: "suave" }, `Si ${p.si.join(" y ")}.`)))));
}
// ── Informe PDF ───────────────────────────────────────────────
function formularioDeInforme(acciones) {
    const guardada = marcaGuardada();
    let logo = guardada.logo_base64;
    const campo = (id, etiqueta, valor, tipo = "text", max = 120) => {
        const entrada = h("input", { id, type: tipo, value: valor, maxlength: String(max), autocomplete: "off" });
        entrada.value = valor; // `value` como atributo no basta en un campo de color
        return { fila: h("div", { class: "campo" }, h("label", { for: id }, etiqueta), entrada), entrada };
    };
    const nombre = campo("m-nombre", "Nombre del taller", guardada.nombre, "text", 80);
    const color = campo("m-color", "Color del encabezado", guardada.color, "color", 7);
    const contacto = campo("m-contacto", "Teléfono, correo o dirección", guardada.contacto);
    const cliente = campo("s-cliente", "Cliente", "", "text", 80);
    const equipo = campo("s-equipo", "Equipo (marca, modelo, serie)", "", "text", 120);
    const tecnico = campo("s-tecnico", "Técnico", tecnicoGuardado(), "text", 80);
    const observaciones = h("textarea", { id: "s-obs", rows: "3", maxlength: "500" });
    const estadoLogo = h("p", { class: "suave", id: "estado-logo" }, logo ? "Logo cargado." : "Sin logo (opcional).");
    const archivo = h("input", { id: "m-logo", type: "file", accept: "image/png,image/jpeg" });
    archivo.addEventListener("change", () => {
        const f = archivo.files?.[0];
        if (!f)
            return;
        const problema = problemaConLogo(f.type, f.size);
        if (problema) {
            estadoLogo.textContent = problema;
            archivo.value = "";
            return;
        }
        const lector = new FileReader();
        lector.onload = () => {
            const url = String(lector.result);
            logo = url.slice(url.indexOf(",") + 1);
            estadoLogo.textContent = `Logo cargado: ${f.name}`;
        };
        lector.onerror = () => {
            estadoLogo.textContent = "No se pudo leer el archivo.";
        };
        lector.readAsDataURL(f);
    });
    const quitarLogo = h("button", { class: "boton texto", type: "button", onclick: () => {
            logo = null;
            archivo.value = "";
            estadoLogo.textContent = "Sin logo (opcional).";
        } }, "Quitar logo");
    const mensaje = h("p", { class: "error-campo", role: "alert" });
    const boton = h("button", { class: "boton principal", type: "submit" }, "⬇️ Descargar informe PDF");
    const enviar = async (e) => {
        e.preventDefault();
        mensaje.textContent = "";
        if (!esColorValido(color.entrada.value)) {
            mensaje.textContent = "El color no es válido.";
            return;
        }
        const marca = {
            nombre: nombre.entrada.value.trim() || "Informe de diagnóstico",
            color: color.entrada.value,
            contacto: contacto.entrada.value.trim(),
            logo_base64: logo,
        };
        guardarMarca({ ...marca, nombre: nombre.entrada.value.trim() });
        guardarTecnico(tecnico.entrada.value.trim());
        boton.disabled = true;
        boton.textContent = "Generando…";
        try {
            await acciones.descargarInforme(marca, {
                cliente: cliente.entrada.value.trim(),
                equipo: equipo.entrada.value.trim(),
                tecnico: tecnico.entrada.value.trim(),
                observaciones: observaciones.value.trim(),
            });
        }
        catch (error) {
            mensaje.textContent = error instanceof Error ? error.message : "No se pudo generar el informe.";
        }
        finally {
            boton.disabled = false;
            boton.textContent = "⬇️ Descargar informe PDF";
        }
    };
    return h("section", { class: "tarjeta", "aria-labelledby": "titulo-informe" }, h("h2", { id: "titulo-informe" }, "Informe para el cliente"), h("p", { class: "ayuda" }, "Genera un PDF con la marca de tu taller para entregar al cliente. Pedirlo no cuenta como otra consulta."), h("form", { class: "informe", onsubmit: (e) => void enviar(e) }, h("fieldset", {}, h("legend", {}, "Tu taller"), nombre.fila, color.fila, contacto.fila, h("div", { class: "campo" }, h("label", { for: "m-logo" }, "Logo (PNG o JPG, hasta 500 KB)"), archivo, estadoLogo, quitarLogo)), h("fieldset", {}, h("legend", {}, "Este servicio"), cliente.fila, equipo.fila, tecnico.fila, h("div", { class: "campo" }, h("label", { for: "s-obs" }, "Observaciones"), observaciones)), mensaje, boton));
}
