// Ayuda mínima para armar el DOM. Todo el texto entra con textContent, nunca con innerHTML,
// así que nada de lo que venga de la API o del usuario puede inyectar HTML.

type Hijo = Node | string | number | null | false | undefined;
type Atributo = string | boolean | EventListener | undefined;

export function h<K extends keyof HTMLElementTagNameMap>(
  etiqueta: K,
  atributos: Record<string, Atributo> = {},
  ...hijos: Hijo[]
): HTMLElementTagNameMap[K] {
  const elemento = document.createElement(etiqueta);
  for (const [nombre, valor] of Object.entries(atributos)) {
    if (valor === undefined || valor === false) continue;
    if (typeof valor === "function") {
      elemento.addEventListener(nombre.replace(/^on/, ""), valor);
    } else if (valor === true) {
      elemento.setAttribute(nombre, "");
    } else {
      elemento.setAttribute(nombre, valor);
    }
  }
  for (const hijo of hijos) {
    if (hijo === null || hijo === false || hijo === undefined) continue;
    elemento.append(typeof hijo === "number" ? String(hijo) : hijo);
  }
  return elemento;
}

export function vaciar(elemento: Element): void {
  elemento.replaceChildren();
}
