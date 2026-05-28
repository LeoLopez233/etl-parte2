# app.py
# Evaluación 2 - Parte 2
# Arquitectura y Almacenamiento de Datos
# Docente: Hernán R. Sáez Talavera
# Motor de Base de Datos: SQLite

from flask import Flask, request, render_template, send_file, jsonify
import sqlite3
import os
import re
from datetime import datetime, date

app = Flask(__name__)

# Carpeta donde se guardan las bases de datos y archivos exportados
CARPETA = "uploads"
os.makedirs(CARPETA, exist_ok=True)

# Rutas de las bases de datos
DB_FAMOSOS = os.path.join(CARPETA, "famosos.db")
DB_LUGARES = os.path.join(CARPETA, "lugares.db")


# =============================================================
# EJERCICIO I - FAMOSOS Y FECHAS
# =============================================================

# -------------------------------------------------------------
# Crear las tablas de famosos en SQLite
# -------------------------------------------------------------
def crear_tablas_famosos():
    # Conectar a la base de datos (la crea si no existe)
    conn = sqlite3.connect(DB_FAMOSOS)
    c = conn.cursor()

    # Tabla con los datos originales del archivo
    c.execute("""
        CREATE TABLE IF NOT EXISTS FAMOSOS_RAW (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            linea TEXT
        )
    """)

    # Tabla con los datos ya normalizados
    c.execute("""
        CREATE TABLE IF NOT EXISTS FAMOSOS_NORM (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            fecha_nacimiento TEXT,
            edad INTEGER,
            es_cumpleanos INTEGER
        )
    """)

    # Tabla para guardar un registro de los cambios que se hicieron
    c.execute("""
        CREATE TABLE IF NOT EXISTS LOG_FAMOSOS (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            numero_linea INTEGER,
            tipo_cambio TEXT,
            valor_antes TEXT,
            valor_despues TEXT
        )
    """)

    conn.commit()
    conn.close()


# -------------------------------------------------------------
# Vaciar las tablas antes de cargar un nuevo archivo
# -------------------------------------------------------------
def vaciar_tablas_famosos():
    conn = sqlite3.connect(DB_FAMOSOS)
    c = conn.cursor()
    c.execute("DELETE FROM FAMOSOS_RAW")
    c.execute("DELETE FROM FAMOSOS_NORM")
    c.execute("DELETE FROM LOG_FAMOSOS")
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# Guardar un cambio en el log
# -------------------------------------------------------------
def guardar_log_famosos(numero_linea, tipo, antes, despues):
    conn = sqlite3.connect(DB_FAMOSOS)
    c = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO LOG_FAMOSOS (fecha_hora, numero_linea, tipo_cambio, valor_antes, valor_despues)
        VALUES (?, ?, ?, ?, ?)
    """, (ahora, numero_linea, tipo, antes, despues))
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# Convertir una fecha al formato DD-MM-YYYY
# El archivo tiene fechas en varios formatos distintos
# -------------------------------------------------------------
def normalizar_fecha(fecha_texto, numero_linea):
    fecha_texto = fecha_texto.strip()

    # Si la fecha tiene "a.C." o "alrededor" no se puede normalizar
    if "a.C" in fecha_texto or "alrededor" in fecha_texto.lower():
        guardar_log_famosos(numero_linea, "FECHA_NO_PARSEABLE", fecha_texto, "NULL")
        return None

    # Lista de formatos que puede tener la fecha en el archivo
    formatos_posibles = [
        "%Y-%m-%d",   # 1879-03-14
        "%Y/%m/%d",   # 1879/03/14
        "%d-%m-%Y",   # 14-03-1879
        "%d/%m/%Y",   # 14/03/1879
    ]

    # Probar cada formato hasta que uno funcione
    for formato in formatos_posibles:
        try:
            fecha = datetime.strptime(fecha_texto, formato)
            fecha_normalizada = fecha.strftime("%d-%m-%Y")

            # Solo guardar en el log si la fecha cambió de formato
            if fecha_normalizada != fecha_texto:
                guardar_log_famosos(numero_linea, "FECHA_NORMALIZADA", fecha_texto, fecha_normalizada)

            return fecha_normalizada
        except ValueError:
            # Si el formato no coincide, probar el siguiente
            continue

    # Si ningún formato funcionó
    guardar_log_famosos(numero_linea, "FECHA_DESCONOCIDA", fecha_texto, "NULL")
    return None


# -------------------------------------------------------------
# Calcular cuántos años tiene una persona según su fecha de nacimiento
# -------------------------------------------------------------
def calcular_edad(fecha_str):
    if not fecha_str:
        return None

    try:
        nacimiento = datetime.strptime(fecha_str, "%d-%m-%Y").date()
        hoy = date.today()

        # Calcular años
        edad = hoy.year - nacimiento.year

        # Si todavía no llegó el cumpleaños este año, restar 1
        if (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day):
            edad -= 1

        return edad
    except:
        return None


# -------------------------------------------------------------
# Revisar si hoy es el cumpleaños de la persona
# Retorna 1 si es cumpleaños, 0 si no
# -------------------------------------------------------------
def revisar_cumpleanos(fecha_str):
    if not fecha_str:
        return 0

    try:
        nacimiento = datetime.strptime(fecha_str, "%d-%m-%Y").date()
        hoy = date.today()

        if nacimiento.month == hoy.month and nacimiento.day == hoy.day:
            return 1
        return 0
    except:
        return 0


# -------------------------------------------------------------
# Proceso ETL completo para el archivo de famosos
# -------------------------------------------------------------
def procesar_archivo_famosos(lineas):
    crear_tablas_famosos()
    vaciar_tablas_famosos()

    # Guardar todas las líneas originales en FAMOSOS_RAW
    conn = sqlite3.connect(DB_FAMOSOS)
    c = conn.cursor()
    for linea in lineas:
        if linea.strip() != "":
            c.execute("INSERT INTO FAMOSOS_RAW (linea) VALUES (?)", (linea.strip(),))
    conn.commit()
    conn.close()

    # Leer los datos originales para procesarlos
    conn = sqlite3.connect(DB_FAMOSOS)
    c = conn.cursor()
    c.execute("SELECT id, linea FROM FAMOSOS_RAW ORDER BY id")
    registros = c.fetchall()
    conn.close()

    # Contadores para las estadísticas
    total_original  = len(registros)
    total_duplicados = 0
    total_invalidos  = 0
    total_ok         = 0

    # Conjunto para detectar duplicados (usamos minúsculas para comparar)
    ya_vistos = set()

    for (numero_linea, linea_original) in registros:

        # Paso 1: Quitar el número al inicio ("1. ", "25. ", etc.)
        linea = re.sub(r"^\d+\.\s*", "", linea_original).strip()
        if linea != linea_original:
            guardar_log_famosos(numero_linea, "NUMERO_ELIMINADO", linea_original, linea)

        # Paso 2: Separar el nombre de la fecha (vienen separados por " - ")
        if " - " not in linea:
            guardar_log_famosos(numero_linea, "FORMATO_INVALIDO", linea, "DESCARTADO")
            total_invalidos += 1
            continue

        nombre    = linea.split(" - ")[0].strip()
        fecha_raw = linea.split(" - ")[1].strip()

        # Paso 3: Normalizar la fecha al formato DD-MM-YYYY
        fecha_ok = normalizar_fecha(fecha_raw, numero_linea)

        # Paso 4: Revisar si este registro ya fue procesado (duplicado)
        clave = nombre.lower() + "|" + str(fecha_ok)
        if clave in ya_vistos:
            guardar_log_famosos(numero_linea, "DUPLICADO_ELIMINADO", linea_original, nombre)
            total_duplicados += 1
            continue
        ya_vistos.add(clave)

        # Paso 5: Calcular edad y revisar si hoy es su cumpleaños
        edad     = calcular_edad(fecha_ok)
        cumple   = revisar_cumpleanos(fecha_ok)

        # Paso 6: Guardar en FAMOSOS_NORM
        conn = sqlite3.connect(DB_FAMOSOS)
        c = conn.cursor()
        c.execute("""
            INSERT INTO FAMOSOS_NORM (nombre, fecha_nacimiento, edad, es_cumpleanos)
            VALUES (?, ?, ?, ?)
        """, (nombre, fecha_ok, edad, cumple))
        conn.commit()
        conn.close()
        total_ok += 1

    return {
        "total_original" : total_original,
        "total_duplicados": total_duplicados,
        "total_invalidos" : total_invalidos,
        "total_ok"        : total_ok
    }


# -------------------------------------------------------------
# Obtener todos los famosos normalizados para mostrar en pantalla
# -------------------------------------------------------------
def obtener_famosos():
    conn = sqlite3.connect(DB_FAMOSOS)
    c = conn.cursor()
    c.execute("SELECT id, nombre, fecha_nacimiento, edad, es_cumpleanos FROM FAMOSOS_NORM ORDER BY nombre")
    datos = c.fetchall()
    conn.close()
    return datos


# -------------------------------------------------------------
# Obtener el log de cambios de famosos
# -------------------------------------------------------------
def obtener_log_famosos():
    conn = sqlite3.connect(DB_FAMOSOS)
    c = conn.cursor()
    c.execute("SELECT fecha_hora, numero_linea, tipo_cambio, valor_antes, valor_despues FROM LOG_FAMOSOS ORDER BY id")
    datos = c.fetchall()
    conn.close()
    return datos


# =============================================================
# EJERCICIO II - LUGARES Y UBICACIONES
# =============================================================

# -------------------------------------------------------------
# Crear las tablas de lugares en SQLite
# -------------------------------------------------------------
def crear_tablas_lugares():
    conn = sqlite3.connect(DB_LUGARES)
    c = conn.cursor()

    # Datos originales del archivo
    c.execute("""
        CREATE TABLE IF NOT EXISTS LUGARES_RAW (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            direccion TEXT,
            georeferencia TEXT
        )
    """)

    # Tabla 1: solo el nombre del lugar
    c.execute("""
        CREATE TABLE IF NOT EXISTS Lugares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE
        )
    """)

    # Tabla 2: coordenadas geográficas
    c.execute("""
        CREATE TABLE IF NOT EXISTS Georeferencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lugar_id INTEGER,
            latitud REAL,
            longitud REAL
        )
    """)

    # Tabla 3: dirección desglosada en partes
    c.execute("""
        CREATE TABLE IF NOT EXISTS Direcciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lugar_id INTEGER,
            nombre_calle TEXT,
            numero_calle TEXT,
            ciudad_estado_provincia TEXT,
            pais TEXT
        )
    """)

    # Log de cambios
    c.execute("""
        CREATE TABLE IF NOT EXISTS LOG_LUGARES (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            tipo_cambio TEXT,
            detalle TEXT
        )
    """)

    conn.commit()
    conn.close()


# -------------------------------------------------------------
# Vaciar las tablas antes de una nueva carga
# -------------------------------------------------------------
def vaciar_tablas_lugares():
    conn = sqlite3.connect(DB_LUGARES)
    c = conn.cursor()
    c.execute("DELETE FROM LUGARES_RAW")
    c.execute("DELETE FROM Lugares")
    c.execute("DELETE FROM Georeferencias")
    c.execute("DELETE FROM Direcciones")
    c.execute("DELETE FROM LOG_LUGARES")
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# Guardar un evento en el log de lugares
# -------------------------------------------------------------
def guardar_log_lugares(tipo, detalle):
    conn = sqlite3.connect(DB_LUGARES)
    c = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO LOG_LUGARES (fecha_hora, tipo_cambio, detalle)
        VALUES (?, ?, ?)
    """, (ahora, tipo, detalle))
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# Separar la dirección completa en sus partes
# Ejemplo: "1600 Amphitheatre Pkwy, Mountain View, CA, USA"
#       → nombre_calle="Amphitheatre Pkwy", numero="1600",
#         ciudad="Mountain View, CA", pais="USA"
# -------------------------------------------------------------
def separar_direccion(direccion):
    if not direccion:
        return None, None, None, None

    partes = [p.strip() for p in direccion.split(",")]

    # El país es siempre el último fragmento
    pais = partes[-1] if len(partes) >= 1 else None

    # La ciudad/estado es el penúltimo fragmento
    ciudad = partes[-2] if len(partes) >= 2 else None

    # La calle es el primer fragmento
    calle_completa = partes[0] if len(partes) >= 1 else None

    # Intentar separar el número del nombre de la calle
    numero = None
    nombre_calle = calle_completa

    if calle_completa:
        # Buscar si la calle empieza con un número (ej: "1600 Amphitheatre Pkwy")
        coincidencia = re.match(r"^(\d+)\s+(.+)$", calle_completa)
        if coincidencia:
            numero       = coincidencia.group(1)
            nombre_calle = coincidencia.group(2)

    return nombre_calle, numero, ciudad, pais


# -------------------------------------------------------------
# Separar la georeferencia en latitud y longitud
# Ejemplo: "37.422, -122.084" → lat=37.422, lng=-122.084
# -------------------------------------------------------------
def separar_georeferencia(georef):
    if not georef:
        return None, None

    try:
        partes = georef.split(",")
        lat = float(partes[0].strip())
        lng = float(partes[1].strip())
        return lat, lng
    except:
        return None, None


# -------------------------------------------------------------
# Proceso ETL completo para el archivo de lugares
# -------------------------------------------------------------
def procesar_archivo_lugares(lineas):
    crear_tablas_lugares()
    vaciar_tablas_lugares()

    total_original   = 0
    total_duplicados = 0
    total_ok         = 0

    # Conjunto para detectar duplicados
    ya_vistos = set()

    for linea in lineas:
        linea = linea.strip()

        # Saltar líneas vacías y el encabezado
        if not linea or linea.startswith("Nombre del lugar"):
            continue

        # El archivo usa ";" para separar las columnas
        columnas = linea.split(";")
        if len(columnas) < 2:
            continue

        nombre    = columnas[0].strip()
        direccion = columnas[1].strip() if len(columnas) > 1 else ""
        georef    = columnas[2].strip() if len(columnas) > 2 else ""

        total_original += 1

        # Guardar el dato original en LUGARES_RAW
        conn = sqlite3.connect(DB_LUGARES)
        c = conn.cursor()
        c.execute("INSERT INTO LUGARES_RAW (nombre, direccion, georeferencia) VALUES (?, ?, ?)",
                  (nombre, direccion, georef))
        conn.commit()
        conn.close()

        # Revisar si este lugar ya fue procesado (duplicado)
        clave = nombre.lower() + "|" + georef
        if clave in ya_vistos:
            guardar_log_lugares("DUPLICADO_ELIMINADO", nombre + " | " + georef)
            total_duplicados += 1
            continue
        ya_vistos.add(clave)

        # Insertar en tabla Lugares
        conn = sqlite3.connect(DB_LUGARES)
        c = conn.cursor()

        # Intentar insertar el nombre del lugar
        try:
            c.execute("INSERT INTO Lugares (nombre) VALUES (?)", (nombre,))
            lugar_id = c.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            # Si ya existe ese nombre, buscar su ID
            conn.rollback()
            c.execute("SELECT id FROM Lugares WHERE nombre = ?", (nombre,))
            fila = c.fetchone()
            lugar_id = fila[0] if fila else None

        # Si no tenemos un ID válido, saltamos este registro
        if not lugar_id:
            conn.close()
            continue

        # Insertar en Georeferencias
        lat, lng = separar_georeferencia(georef)
        c.execute("""
            INSERT INTO Georeferencias (lugar_id, latitud, longitud)
            VALUES (?, ?, ?)
        """, (lugar_id, lat, lng))

        # Insertar en Direcciones
        nombre_calle, numero, ciudad, pais = separar_direccion(direccion)
        c.execute("""
            INSERT INTO Direcciones (lugar_id, nombre_calle, numero_calle, ciudad_estado_provincia, pais)
            VALUES (?, ?, ?, ?, ?)
        """, (lugar_id, nombre_calle, numero, ciudad, pais))

        conn.commit()
        conn.close()
        total_ok += 1

    return {
        "total_original"  : total_original,
        "total_duplicados": total_duplicados,
        "total_ok"        : total_ok
    }


# -------------------------------------------------------------
# Obtener todos los lugares con sus datos para mostrar en pantalla
# -------------------------------------------------------------
def obtener_lugares():
    conn = sqlite3.connect(DB_LUGARES)
    c = conn.cursor()
    # Unir las 3 tablas en una sola consulta
    c.execute("""
        SELECT
            l.id, l.nombre,
            g.latitud, g.longitud,
            d.nombre_calle, d.numero_calle,
            d.ciudad_estado_provincia, d.pais
        FROM Lugares l
        LEFT JOIN Georeferencias g ON g.lugar_id = l.id
        LEFT JOIN Direcciones d    ON d.lugar_id = l.id
        ORDER BY l.nombre
    """)
    datos = c.fetchall()
    conn.close()
    return datos


# -------------------------------------------------------------
# Obtener el log de cambios de lugares
# -------------------------------------------------------------
def obtener_log_lugares():
    conn = sqlite3.connect(DB_LUGARES)
    c = conn.cursor()
    c.execute("SELECT fecha_hora, tipo_cambio, detalle FROM LOG_LUGARES ORDER BY id")
    datos = c.fetchall()
    conn.close()
    return datos


# =============================================================
# RUTAS FLASK - Lo que el navegador puede pedir al servidor
# =============================================================

# Página principal
@app.route("/")
def pagina_principal():
    return render_template("index.html")


# ── Ejercicio I ──────────────────────────────────────────────

@app.route("/procesar/famosos", methods=["POST"])
def ruta_famosos():
    # Verificar que se subió un archivo
    if "archivo" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400

    archivo = request.files["archivo"]
    contenido = archivo.read().decode("utf-8", errors="replace")
    lineas = contenido.split("\n")

    # Ejecutar el proceso ETL
    stats   = procesar_archivo_famosos(lineas)
    famosos = obtener_famosos()
    log     = obtener_log_famosos()

    # Devolver los resultados en formato JSON al navegador
    return jsonify({
        "stats": stats,
        "famosos": [
            {
                "id"             : f[0],
                "nombre"         : f[1],
                "fecha_nacimiento": f[2] or "No disponible",
                "edad"           : f[3] if f[3] is not None else "–",
                "es_cumpleanos"  : bool(f[4])
            }
            for f in famosos
        ],
        "log": [
            {
                "fecha"  : l[0],
                "linea"  : l[1],
                "tipo"   : l[2],
                "antes"  : l[3],
                "despues": l[4]
            }
            for l in log
        ]
    })


@app.route("/descargar/famosos/csv")
def descargar_famosos():
    famosos = obtener_famosos()
    ruta = os.path.join(CARPETA, "FAMOSOS_NORM.csv")

    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write("id,nombre,fecha_nacimiento,edad,es_cumpleanos\n")
        for f in famosos:
            cumple = "SI" if f[4] else "NO"
            archivo.write(f'{f[0]},"{f[1]}",{f[2] or ""},{ f[3] or ""},{ cumple}\n')

    return send_file(ruta, as_attachment=True)


@app.route("/descargar/famosos/log")
def descargar_log_famosos():
    log  = obtener_log_famosos()
    ruta = os.path.join(CARPETA, "FAMOSOS_log.txt")

    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write(f"LOG DE CAMBIOS - FAMOSOS\n")
        archivo.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        archivo.write("=" * 50 + "\n\n")
        for l in log:
            archivo.write(f"[{l[0]}] Linea {l[1]} | {l[2]}\n")
            archivo.write(f"  ANTES  : {l[3]}\n")
            archivo.write(f"  DESPUES: {l[4]}\n\n")

    return send_file(ruta, as_attachment=True)


# ── Ejercicio II ─────────────────────────────────────────────

@app.route("/procesar/lugares", methods=["POST"])
def ruta_lugares():
    if "archivo" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400

    archivo = request.files["archivo"]
    contenido = archivo.read().decode("utf-8", errors="replace")
    lineas = contenido.split("\n")

    stats   = procesar_archivo_lugares(lineas)
    lugares = obtener_lugares()
    log     = obtener_log_lugares()

    return jsonify({
        "stats": stats,
        "lugares": [
            {
                "id"    : l[0],
                "nombre": l[1],
                "lat"   : l[2],
                "lng"   : l[3],
                "calle" : l[4] or "–",
                "numero": l[5] or "–",
                "ciudad": l[6] or "–",
                "pais"  : l[7] or "–"
            }
            for l in lugares
        ],
        "log": [
            {
                "fecha"   : l[0],
                "tipo"    : l[1],
                "detalle" : l[2]
            }
            for l in log
        ]
    })


@app.route("/descargar/lugares/csv")
def descargar_lugares():
    lugares = obtener_lugares()
    ruta = os.path.join(CARPETA, "DIRECCIONES_NORM.csv")

    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write("id,lugar,nombre_calle,numero_calle,ciudad_estado_provincia,pais,latitud,longitud\n")
        for l in lugares:
            archivo.write(f'{l[0]},"{l[1]}","{l[4] or ""}","{l[5] or ""}","{l[6] or ""}","{l[7] or ""}",{l[2] or ""},{l[3] or ""}\n')

    return send_file(ruta, as_attachment=True)


@app.route("/descargar/lugares/log")
def descargar_log_lugares():
    log  = obtener_log_lugares()
    ruta = os.path.join(CARPETA, "LUGARES_log.txt")

    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write(f"LOG DE CAMBIOS - LUGARES\n")
        archivo.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        archivo.write("=" * 50 + "\n\n")
        for l in log:
            archivo.write(f"[{l[0]}] {l[1]}\n")
            archivo.write(f"  Detalle: {l[2]}\n\n")

    return send_file(ruta, as_attachment=True)


# =============================================================
# INICIAR EL SERVIDOR
# =============================================================
@app.route("/ping")
def ping():
    return "OK", 200
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  ETL Parte 2 - Famosos y Lugares")
    print("  Motor de BD: SQLite")
    print("  Abre el navegador en: http://localhost:5000")
    print("=" * 50 + "\n")
    app.run(debug=True)
