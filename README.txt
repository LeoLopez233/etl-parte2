# ETL Parte 2 — Famosos y Lugares
Evaluación 2, Parte 2 · Arquitectura y Almacenamiento de Datos
Docente: Hernán R. Sáez Talavera · Sede Concepción-Talcahuano

## Cómo ejecutar

1. Instalar Flask (solo la primera vez):
   pip install flask

2. Ejecutar la aplicación:
   python app.py

3. Abrir en el navegador:
   http://localhost:5000

## Archivos de prueba incluidos
- DATOS2026-2.txt  → Ejercicio I (famosos y fechas)
- DATOS2026-3.TXT  → Ejercicio II (lugares y ubicaciones)

## Tablas SQLite creadas
Ejercicio I  → famosos.db  : FAMOSOS_RAW, FAMOSOS_NORM, LOG_FAMOSOS
Ejercicio II → lugares.db  : LUGARES_RAW, Lugares, Georeferencias, Direcciones, LOG_LUGARES
