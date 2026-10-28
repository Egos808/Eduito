"""
Inicializa la base de datos database.db a partir de schema.sql
y carga los datos semilla descritos en el documento técnico:
 - 4 bloques académicos
 - 9 áreas curriculares
 - 6 criterios de evaluación actitudinal
 - 1 usuario docente por defecto (usuario: docente / contraseña: docente123)

Ejecutar una sola vez (o borrar database.db y volver a ejecutar para reiniciar).
"""
import sqlite3
import os
from datetime import date
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

AREAS = [
    ("Comunicación y Lenguaje L-1", "COM-L1"),
    ("Comunicación y Lenguaje L-2", "COM-L2"),
    ("Comunicación y Lenguaje L-3", "COM-L3"),
    ("Matemáticas", "MAT"),
    ("Medio Social y Natural", "MSN"),
    ("Expresión Artística", "ART"),
    ("Educación Física", "EDF"),
    ("Formación Ciudadana", "FCI"),
    ("Computación", "COMP"),
]

BLOQUES = [
    ("I Bloque", 1),
    ("II Bloque", 2),
    ("III Bloque", 3),
    ("IV Bloque", 4),
]

CRITERIOS = [
    "Asiste regularmente a clases",
    "Es puntual",
    "Respeta las pertenencias de los demás",
    "Respeta a sus compañeros",
    "Cumple en traer sus materiales",
    "Participa en las diferentes actividades",
]


def main():
    fresh = not os.path.exists(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    con.executescript(open(SCHEMA_PATH, encoding="utf-8").read())

    cur = con.cursor()

    # Migración: versiones anteriores usaban la columna "codigo" en vez de "clave"
    cur.execute("PRAGMA table_info(estudiantes)")
    columnas = [c[1] for c in cur.fetchall()]
    if "codigo" in columnas and "clave" not in columnas:
        cur.execute("ALTER TABLE estudiantes RENAME COLUMN codigo TO clave")

    # Usuario docente por defecto
    cur.execute("SELECT COUNT(*) FROM usuarios")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO usuarios (usuario, contrasena, nombre, rol, estado) VALUES (?,?,?,?,?)",
            ("docente", generate_password_hash("docente123"), "Docente", "docente", "activo"),
        )
        print("Usuario creado -> usuario: docente / contraseña: docente123 (cámbiala luego de iniciar sesión)")

    # Bloques
    cur.execute("SELECT COUNT(*) FROM bloques")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO bloques (nombre, numero) VALUES (?,?)", BLOQUES
        )

    # Áreas
    cur.execute("SELECT COUNT(*) FROM areas")
    if cur.fetchone()[0] == 0:
        for i, (nombre, codigo) in enumerate(AREAS):
            cur.execute(
                "INSERT INTO areas (nombre, codigo, orden) VALUES (?,?,?)",
                (nombre, codigo, i),
            )

    # Criterios actitudinales
    cur.execute("SELECT COUNT(*) FROM criterios_actitudinales")
    if cur.fetchone()[0] == 0:
        for i, nombre in enumerate(CRITERIOS):
            cur.execute(
                "INSERT INTO criterios_actitudinales (nombre, orden) VALUES (?,?)",
                (nombre, i),
            )
    else:
        # Migración: actualiza el texto de criterios de versiones anteriores
        MIGRACION_CRITERIOS = {
            "Cumple en clase": "Respeta las pertenencias de los demás",
            "Cumple en tareas": "Cumple en traer sus materiales",
        }
        for viejo, nuevo in MIGRACION_CRITERIOS.items():
            cur.execute(
                "UPDATE criterios_actitudinales SET nombre=? WHERE nombre=?", (nuevo, viejo)
            )

    # Configuración general (usada también en el membrete de impresión)
    cur.execute("SELECT COUNT(*) FROM configuracion")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO configuracion (clave, valor) VALUES (?,?)",
            [
                ("ministerio", "MINISTERIO DE EDUCACIÓN"),
                ("direccion_departamental", "DIRECCIÓN DEPARTAMENTAL DE EDUCACIÓN"),
                ("supervision_educativa", "SUPERVISIÓN EDUCATIVA"),
                ("distrito_escolar", "DISTRITO ESCOLAR No. 07-01-04"),
                ("nombre_establecimiento",
                 "ESCUELA OFICIAL RURAL MIXTA: Jornada Vespertina, Aldea San Juan Argueta, Sololá"),
                ("grado", "Segundo"),
                ("seccion", "A"),
                ("nombre_docente", "Docente"),
                ("nombre_directora", "Rosaura Lorena Casia Cutz"),
                ("ciclo_escolar", str(date.today().year)),
            ],
        )
    else:
        # Agrega claves nuevas si la base de datos ya existía de una versión anterior
        nuevas = {
            "ministerio": "MINISTERIO DE EDUCACIÓN",
            "direccion_departamental": "DIRECCIÓN DEPARTAMENTAL DE EDUCACIÓN",
            "supervision_educativa": "SUPERVISIÓN EDUCATIVA",
            "distrito_escolar": "DISTRITO ESCOLAR No. 07-01-04",
            "seccion": "A",
            "nombre_directora": "Rosaura Lorena Casia Cutz",
            "ciclo_escolar": str(date.today().year),
        }
        for k, v in nuevas.items():
            cur.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?,?)", (k, v))

    con.commit()
    con.close()
    print(f"Base de datos lista en: {DB_PATH}" + (" (nueva)" if fresh else " (actualizada)"))


if __name__ == "__main__":
    main()
