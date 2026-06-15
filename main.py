# ================================================================
# SISTEMA EXPERTO: Diagnóstico de PC
# Implementación con motor de inferencia hacia adelante
# Versión extendida: desafíos 1, 2, 3 y 4 implementados
# ================================================================

import json

# ──────────────────────────────────────────────────────────────
# COMPONENTE 1: BASE DE CONOCIMIENTO
# Cada regla tiene: id, condiciones (lista de síntomas requeridos),
# conclusión y un factor de confianza de 0 a 1.
# ──────────────────────────────────────────────────────────────

base_de_conocimiento = [
    # ── Reglas originales ──────────────────────────────────────
    {
        "id": "R01",
        "descripcion": "Fuente de poder dañada",
        "condiciones": ["no_enciende", "sin_luces", "sin_sonido"],
        "conclusion": "Revisar o reemplazar la fuente de poder",
        "confianza": 0.92
    },
    {
        "id": "R02",
        "descripcion": "Falla de RAM",
        "condiciones": ["enciende", "pitidos_arranque", "sin_video"],
        "conclusion": "Probar con módulos de RAM de a uno",
        "confianza": 0.88
    },
    {
        "id": "R03",
        "descripcion": "Falla de tarjeta de video",
        "condiciones": ["enciende", "pantalla_negra", "sin_pitidos"],
        "conclusion": "Revisar tarjeta de video y conexiones del monitor",
        "confianza": 0.80
    },
    {
        "id": "R04",
        "descripcion": "Problemas de almacenamiento",
        "condiciones": ["enciende", "inicia_lento", "disco_al_100"],
        "conclusion": "Verificar salud del disco duro con herramienta SMART",
        "confianza": 0.85
    },
    {
        "id": "R05",
        "descripcion": "Infección por malware",
        "condiciones": ["enciende", "inicia_lento", "ventilador_siempre_activo"],
        "conclusion": "Escanear con antivirus y revisar procesos en segundo plano",
        "confianza": 0.72
    },
    {
        "id": "R06",
        "descripcion": "Driver o RAM dañada",
        "condiciones": ["enciende", "pantalla_azul_frecuente"],
        "conclusion": "Actualizar drivers y testear memoria RAM con MemTest86",
        "confianza": 0.87
    },
    {
        "id": "R07",
        "descripcion": "Sobrecalentamiento",
        "condiciones": ["enciende", "se_apaga_solo", "calor_excesivo"],
        "conclusion": "Limpiar ventiladores y reaplicar pasta térmica",
        "confianza": 0.90
    },

    # ── Desafío 1: 3 reglas nuevas ────────────────────────────
    # Justificación: cubren escenarios frecuentes no contemplados
    # en el código original: falla de BIOS, problemas de red y
    # teclado/periféricos sin respuesta.
    {
        "id": "R08",
        "descripcion": "CMOS / Batería de BIOS agotada",
        "condiciones": ["enciende", "fecha_hora_incorrecta", "pitidos_arranque"],
        "conclusion": "Reemplazar la pila CR2032 de la placa madre",
        "confianza": 0.83
    },
    {
        "id": "R09",
        "descripcion": "Falla de adaptador de red / drivers WiFi",
        "condiciones": ["enciende", "sin_conexion_red", "otras_apps_funcionan"],
        "conclusion": "Reinstalar drivers de red o reemplazar adaptador WiFi",
        "confianza": 0.78
    },
    {
        "id": "R10",
        "descripcion": "Falla de controlador USB",
        "condiciones": ["enciende", "perifericos_no_responden", "sin_pitidos"],
        "conclusion": "Desinstalar y reinstalar controladores USB en el Administrador de dispositivos",
        "confianza": 0.75
    },
]

# ──────────────────────────────────────────────────────────────
# COMPONENTE 2: BASE DE HECHOS (Working Memory)
# Set de Python: búsqueda O(1) y no permite duplicados.
# ──────────────────────────────────────────────────────────────

base_de_hechos = set()

# ──────────────────────────────────────────────────────────────
# COMPONENTE 3: MOTOR DE INFERENCIA
# ──────────────────────────────────────────────────────────────

def equiparar(base_conocimiento, hechos):
    """
    Pattern matching: retorna todas las reglas cuyas condiciones
    están completamente satisfechas por los hechos actuales.
    Usa set.issubset() para eficiencia O(n).
    """
    conflict_set = []
    for regla in base_conocimiento:
        if set(regla['condiciones']).issubset(hechos):
            conflict_set.append(regla)
    return conflict_set


def resolver_conflictos(conflict_set):
    """
    Resolución de conflictos: mayor confianza primero.
    Desempate por número de condiciones (regla más específica).
    Retorna solo la mejor regla (comportamiento original).
    """
    if not conflict_set:
        return None
    return max(
        conflict_set,
        key=lambda r: (r['confianza'], len(r['condiciones']))
    )


# ── Desafío 2: Múltiples diagnósticos ordenados ───────────────
# Justificación: en diagnóstico real un equipo puede presentar
# varios problemas simultáneos. Mostrar el ranking completo ayuda
# al técnico a no descartar causas secundarias.

def resolver_todos(conflict_set):
    """
    Retorna TODOS los diagnósticos posibles ordenados de mayor
    a menor confianza (y por especificidad como desempate).
    """
    return sorted(
        conflict_set,
        key=lambda r: (r['confianza'], len(r['condiciones'])),
        reverse=True
    )


def inferir(base_conocimiento, hechos, mostrar_todos=False):
    """
    Motor de inferencia principal.
    Ciclo: equiparación → resolución de conflictos → ejecución.
    Parámetro mostrar_todos activa el Desafío 2.
    """
    print()
    print('━' * 55)
    print('  MOTOR DE INFERENCIA INICIADO')
    print('━' * 55)
    print(f'  Hechos ingresados: {hechos}')
    print()

    conflict_set = equiparar(base_conocimiento, hechos)

    if not conflict_set:
        print('  ⚠ No se encontraron reglas aplicables.')
        print('  Considera agregar más síntomas o revisar la base de conocimiento.')
        return

    print(f'  Reglas que aplican (conflict set): {[r["id"] for r in conflict_set]}')
    print()

    if mostrar_todos:
        # ── Desafío 2: ranking completo ──────────────────────
        ranking = resolver_todos(conflict_set)
        print('  RANKING COMPLETO DE DIAGNÓSTICOS')
        print('  ───────────────────────────────────────────────────')
        for i, regla in enumerate(ranking, 1):
            print(f'  #{i} [{regla["id"]}] {regla["descripcion"]}')
            print(f'      → {regla["conclusion"]}')
            print(f'      Confianza: {regla["confianza"] * 100:.0f}%')
            print()
        regla = ranking[0]  # la mejor para la trazabilidad
    else:
        regla = resolver_conflictos(conflict_set)
        print('  DIAGNÓSTICO PRINCIPAL')
        print('  ───────────────────────────────────────────────────')
        print(f'  Regla aplicada: {regla["id"]} — {regla["descripcion"]}')
        print(f'  Recomendación:  {regla["conclusion"]}')
        print(f'  Confianza:      {regla["confianza"] * 100:.0f}%')
        print()

    # COMPONENTE 4: INTERFAZ DE EXPLICACIÓN
    print('  TRAZABILIDAD DEL RAZONAMIENTO')
    print('  ───────────────────────────────────────────────────')
    print(f'  Síntomas que activaron la regla principal: {regla["condiciones"]}')
    if len(conflict_set) > 1 and not mostrar_todos:
        descartadas = [r['id'] for r in conflict_set if r['id'] != regla['id']]
        print(f'  Reglas descartadas por menor confianza: {descartadas}')
    print('━' * 55)


# ── Desafío 3: Encadenamiento hacia atrás ────────────────────
# Justificación: permite al técnico partir de una hipótesis
# (ej. "¿podría ser sobrecalentamiento?") y obtener exactamente
# qué síntomas tendría que confirmar para validarla, sin
# recorrer manualmente la base de conocimiento.

def backward_chain(meta_descripcion, base_conocimiento, hechos, nivel=0):
    """
    Dado un diagnóstico (meta), determina recursivamente qué
    síntomas habría que confirmar para llegar a esa conclusión.

    Parámetros:
        meta_descripcion : str  — descripción o id de la regla objetivo
        base_conocimiento: list — base de conocimiento completa
        hechos           : set  — síntomas ya conocidos
        nivel            : int  — profundidad de recursión (interno)

    Retorna:
        dict con 'regla', 'ya_confirmados' y 'pendientes'
    """
    indent = "  " + "  " * nivel

    # Buscar la regla cuya descripción o id coincida
    regla_meta = None
    for r in base_conocimiento:
        if meta_descripcion.upper() in (r['id'].upper(), r['descripcion'].upper()):
            regla_meta = r
            break

    if regla_meta is None:
        return {"error": f"No se encontró ninguna regla con id/descripción '{meta_descripcion}'"}

    condiciones = set(regla_meta['condiciones'])
    ya_confirmados = condiciones & hechos
    pendientes = condiciones - hechos

    resultado = {
        "regla": regla_meta['id'],
        "descripcion": regla_meta['descripcion'],
        "confianza": regla_meta['confianza'],
        "ya_confirmados": list(ya_confirmados),
        "pendientes": list(pendientes),
        "se_puede_activar": len(pendientes) == 0
    }

    # Recursión: para cada síntoma pendiente, verificar si alguna
    # otra regla lo puede deducir automáticamente como conclusión.
    # (En este sistema los síntomas son atómicos, así que la recursión
    #  sirve de base para sistemas donde los hechos intermedios
    #  son conclusiones de otras reglas.)
    sub_cadenas = {}
    for sintoma in pendientes:
        for r in base_conocimiento:
            if sintoma in r['conclusion']:
                sub_cadenas[sintoma] = backward_chain(
                    r['id'], base_conocimiento, hechos, nivel + 1
                )
    if sub_cadenas:
        resultado["sub_cadenas"] = sub_cadenas

    return resultado


def imprimir_backward(resultado, nivel=0):
    """Imprime el resultado de backward_chain de forma legible."""
    indent = "  " * nivel
    if "error" in resultado:
        print(f"{indent}  ⚠ {resultado['error']}")
        return
    print(f"{indent}  Regla objetivo : {resultado['regla']} — {resultado['descripcion']}")
    print(f"{indent}  Confianza      : {resultado['confianza'] * 100:.0f}%")
    print(f"{indent}  Ya confirmados : {resultado['ya_confirmados'] or '—'}")
    print(f"{indent}  Pendientes     : {resultado['pendientes'] or '—'}")
    se_activa = "✓ SÍ" if resultado['se_puede_activar'] else "✗ NO (faltan síntomas)"
    print(f"{indent}  ¿Se activa?    : {se_activa}")
    if resultado.get("sub_cadenas"):
        print(f"{indent}  Sub-cadenas:")
        for sintoma, sub in resultado["sub_cadenas"].items():
            print(f"{indent}    [{sintoma}]")
            imprimir_backward(sub, nivel + 2)


# ── Desafío 4: Exportar red de inferencia como JSON ──────────
# Justificación: tener el grafo en formato estándar (JSON)
# permite visualizarlo con herramientas externas (Gephi, D3.js,
# Cytoscape) y facilita el mantenimiento de la base de conocimiento.

def exportar_red(base_conocimiento):
    """
    Recorre la base de conocimiento y genera un grafo dirigido:
      - Nodos: síntomas (tipo 'hecho') y conclusiones (tipo 'conclusion')
      - Aristas: de cada síntoma a la conclusión de su regla,
                 etiquetadas con el id y confianza de la regla.
    Retorna un dict con 'nodos' y 'aristas'.
    """
    nodos = {}   # clave: etiqueta, valor: dict con tipo
    aristas = []

    for regla in base_conocimiento:
        # Nodos de tipo hecho (síntomas)
        for condicion in regla['condiciones']:
            if condicion not in nodos:
                nodos[condicion] = {"id": condicion, "tipo": "hecho"}

        # Nodo de tipo conclusión
        clave_conclusion = regla['conclusion']
        if clave_conclusion not in nodos:
            nodos[clave_conclusion] = {
                "id": clave_conclusion,
                "tipo": "conclusion",
                "regla": regla['id'],
                "descripcion": regla['descripcion']
            }

        # Aristas: cada condición → conclusión (etiquetada con la regla)
        for condicion in regla['condiciones']:
            aristas.append({
                "origen": condicion,
                "destino": clave_conclusion,
                "regla": regla['id'],
                "confianza": regla['confianza']
            })

    grafo = {
        "nodos": list(nodos.values()),
        "aristas": aristas
    }
    return grafo


# ──────────────────────────────────────────────────────────────
# COMPONENTE 5: INTERFAZ DE USUARIO
# ──────────────────────────────────────────────────────────────

PREGUNTAS = {
    # Síntomas originales
    "no_enciende":               "¿El equipo NO enciende (sin luces, sin sonido)?",
    "sin_luces":                 "¿No hay ninguna luz LED encendida?",
    "sin_sonido":                "¿No se escucha ningún sonido al encender?",
    "enciende":                  "¿El equipo SÍ enciende (hay luces y/o sonido)?",
    "pitidos_arranque":          "¿Se escuchan pitidos (beeps) al encender?",
    "sin_video":                 "¿La pantalla no muestra absolutamente nada?",
    "pantalla_negra":            "¿La pantalla queda en negro (sin pitidos)?",
    "sin_pitidos":               "¿No se escuchan pitidos?",
    "inicia_lento":              "¿El equipo tarda más de 3 minutos en iniciar?",
    "disco_al_100":              "¿El administrador de tareas muestra disco al 100%?",
    "ventilador_siempre_activo": "¿El ventilador está siempre a máxima velocidad?",
    "pantalla_azul_frecuente":   "¿Aparece pantalla azul (BSOD) con frecuencia?",
    "se_apaga_solo":             "¿El equipo se apaga solo sin advertencia?",
    "calor_excesivo":            "¿El chasis está muy caliente al tacto?",
    # Síntomas nuevos (Desafío 1)
    "fecha_hora_incorrecta":     "¿La fecha y hora se reinician cada vez que apaga el equipo?",
    "sin_conexion_red":          "¿El equipo no se conecta a ninguna red (WiFi/Ethernet)?",
    "otras_apps_funcionan":      "¿Las demás aplicaciones funcionan con normalidad?",
    "perifericos_no_responden":  "¿El teclado o mouse USB no responden al encenderlo?",
}


def consultar():
    print()
    print('=' * 55)
    print('  SISTEMA EXPERTO: Diagnóstico de Computador')
    print('  Responde s (sí) o n (no) a cada pregunta')
    print('=' * 55)
    print()

    for sintoma, pregunta in PREGUNTAS.items():
        while True:
            resp = input(f'  {pregunta} [s/n]: ').strip().lower()
            if resp in ('s', 'n'):
                break
            print('  ⚠ Por favor escribe s o n.')
        if resp == 's':
            base_de_hechos.add(sintoma)

    # Preguntar modalidad: diagnóstico único o ranking completo
    print()
    while True:
        modo = input('  ¿Ver ranking completo de diagnósticos? [s/n]: ').strip().lower()
        if modo in ('s', 'n'):
            break
    mostrar_todos = (modo == 's')

    inferir(base_de_conocimiento, base_de_hechos, mostrar_todos)

    # ── Menú de desafíos extra ─────────────────────────────────
    print()
    print('  OPCIONES ADICIONALES')
    print('  ───────────────────────────────────────────────────')

    while True:
        bc = input('  ¿Ejecutar encadenamiento hacia atrás? [s/n]: ').strip().lower()
        if bc in ('s', 'n'):
            break
    if bc == 's':
        print()
        print('  IDs disponibles: ' + ', '.join(r['id'] for r in base_de_conocimiento))
        meta = input('  Ingresa el ID de la regla a analizar (ej. R07): ').strip()
        print()
        print('━' * 55)
        print('  ENCADENAMIENTO HACIA ATRÁS')
        print('━' * 55)
        resultado_bc = backward_chain(meta, base_de_conocimiento, base_de_hechos)
        imprimir_backward(resultado_bc)
        print('━' * 55)

    print()
    while True:
        exp = input('  ¿Exportar red de inferencia a JSON? [s/n]: ').strip().lower()
        if exp in ('s', 'n'):
            break
    if exp == 's':
        grafo = exportar_red(base_de_conocimiento)
        ruta = 'red_inferencia.json'
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(grafo, f, ensure_ascii=False, indent=2)
        print(f'\n  ✓ Red exportada a: {ruta}')
        print(f'    Nodos  : {len(grafo["nodos"])}')
        print(f'    Aristas: {len(grafo["aristas"])}')
        print()
        print('  Vista previa (primeros 2 nodos y 2 aristas):')
        print(json.dumps({"nodos": grafo["nodos"][:2], "aristas": grafo["aristas"][:2]},
                         ensure_ascii=False, indent=4))


# ── Punto de entrada ──────────────────────────────────────────
if __name__ == '__main__':
    consultar()