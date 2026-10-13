# Interfaz web para talleres

Una aplicación de una sola página, en **TypeScript sin frameworks**, que usa la [API REST](api.md). La sirve la
misma API, así que hay un solo servicio que desplegar:

```bash
python -m uvicorn sistema_experto.api:app
```

Abre <http://localhost:8000/>: redirige a `/app/`.

## Qué hace

1. **Entrar:** el técnico escribe la clave de su taller. Se guarda solo mientras la pestaña esté abierta
   (`sessionStorage`); al cerrarla hay que volver a escribirla. Si la clave deja de valer (revocada, cuenta
   suspendida), la app vuelve a la entrada con el motivo.
2. **Consulta guiada:** una pregunta a la vez, con botones grandes (sí / no / no sé), opciones y campos
   numéricos con unidad y rango. Muestra "¿por qué me preguntas esto?", las pruebas de verificación (con
   "No puedo hacerla" y "ver el diagnóstico sin más pruebas"), el diagnóstico diferencial, el historial de
   respuestas y **deshacer / reiniciar**.
3. **Resultado:** el diagnóstico con su barra de certeza, recomendaciones, advertencias, otras fallas
   posibles, las descartadas y el razonamiento.
4. **Informe PDF:** un formulario con el nombre, color, contacto y logo del taller, y los datos del cliente y el
   equipo. Descarga el PDF. La marca y el nombre del técnico se recuerdan en el navegador; los datos del cliente
   no.
5. **Contador de consultas** del mes en la cabecera (en modo comercial), que se pone ámbar cuando quedan 5 o menos.

Los errores de la API se muestran con un mensaje claro: clave inválida, cuota agotada (`402`), demasiadas
llamadas (`429`, con los segundos de espera) o sin conexión. Si una respuesta no se pudo enviar, la consulta
sigue en la misma pregunta.

Funciona en teléfono, tableta y computadora, con modo claro y oscuro según el sistema, y se puede usar con
teclado y lector de pantalla (el foco pasa al título en cada pregunta).

## Estructura

```
web/
  src/            código TypeScript
    tipos.ts        las formas de los datos de la API
    api.ts          cliente HTTP y manejo de errores
    formato.ts      funciones puras de presentación y validación
    almacen.ts      lo que se recuerda en el navegador
    dom.ts          ayuda para armar el DOM (todo el texto entra con textContent)
    vistas.ts       las pantallas
    app.ts          el estado y el flujo
    main.ts         punto de entrada
  public/         lo que se sirve en /app/
    index.html, css/estilo.css
    js/             JavaScript compilado (se versiona)
  test/           pruebas de la lógica pura (node --test)
```

## Desarrollo

Requiere Node 20 o superior. Solo se necesita para **modificar** la interfaz: el JavaScript compilado está
en el repositorio, así que para usarla basta con Python.

```bash
cd web
npm install
```
```bash
npm run build
```

`npm run watch` recompila al guardar y `npm test` compila y corre las pruebas. **Después de cambiar
`src/` hay que compilar y subir también `public/js/`**: el CI falla si el JavaScript versionado no
corresponde al código fuente.

## Seguridad

- Nada de lo que llega de la API o del usuario se inserta como HTML: se usa `textContent`.
- La clave nunca va en la URL, solo en la cabecera `X-API-Key`.
- Es una interfaz para **técnicos con clave de taller**, no para el público general: la clave viaja desde el
  navegador. Si algún día se ofrece a clientes finales, hará falta un servidor intermedio con inicio de sesión.
- En producción hay que servirla con HTTPS.
