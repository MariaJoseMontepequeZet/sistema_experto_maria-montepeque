// Ayuda mínima para armar el DOM. Todo el texto entra con textContent, nunca con innerHTML,
// así que nada de lo que venga de la API o del usuario puede inyectar HTML.
export function h(etiqueta, atributos = {}, ...hijos) {
    const elemento = document.createElement(etiqueta);
    for (const [nombre, valor] of Object.entries(atributos)) {
        if (valor === undefined || valor === false)
            continue;
        if (typeof valor === "function") {
            elemento.addEventListener(nombre.replace(/^on/, ""), valor);
        }
        else if (valor === true) {
            elemento.setAttribute(nombre, "");
        }
        else {
            elemento.setAttribute(nombre, valor);
        }
    }
    for (const hijo of hijos) {
        if (hijo === null || hijo === false || hijo === undefined)
            continue;
        elemento.append(typeof hijo === "number" ? String(hijo) : hijo);
    }
    return elemento;
}
export function vaciar(elemento) {
    elemento.replaceChildren();
}
