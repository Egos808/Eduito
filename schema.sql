-- Esquema de la base de datos: Sistema de Registro Académico (REGISTRO_MF)

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT UNIQUE NOT NULL,
    contrasena TEXT NOT NULL,
    nombre TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'docente',
    estado TEXT NOT NULL DEFAULT 'activo'
);

CREATE TABLE IF NOT EXISTS estudiantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave TEXT UNIQUE NOT NULL,
    nombres TEXT NOT NULL,
    apellidos TEXT NOT NULL,
    grado TEXT NOT NULL DEFAULT 'Segundo Grado',
    seccion TEXT NOT NULL DEFAULT 'A',
    estado TEXT NOT NULL DEFAULT 'activo'
);

CREATE TABLE IF NOT EXISTS bloques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    numero INTEGER NOT NULL UNIQUE,
    fecha_inicio TEXT,
    fecha_fin TEXT,
    estado TEXT NOT NULL DEFAULT 'activo'
);

CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    codigo TEXT UNIQUE NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'activo'
);

CREATE TABLE IF NOT EXISTS actividades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bloque_id INTEGER NOT NULL REFERENCES bloques(id),
    area_id INTEGER NOT NULL REFERENCES areas(id),
    nombre TEXT NOT NULL,
    tema TEXT,
    fecha_ejecucion TEXT,
    valor_total REAL NOT NULL DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'activo'
);

CREATE TABLE IF NOT EXISTS aspectos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actividad_id INTEGER NOT NULL REFERENCES actividades(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    valor_maximo REAL NOT NULL DEFAULT 0,
    orden INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS calificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL REFERENCES estudiantes(id),
    aspecto_id INTEGER NOT NULL REFERENCES aspectos(id) ON DELETE CASCADE,
    calificacion REAL NOT NULL DEFAULT 0,
    UNIQUE(estudiante_id, aspecto_id)
);

CREATE TABLE IF NOT EXISTS asistencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL REFERENCES estudiantes(id),
    fecha TEXT NOT NULL,
    estado TEXT NOT NULL CHECK(estado IN ('Presente','Ausente','Justificado')),
    UNIQUE(estudiante_id, fecha)
);

CREATE TABLE IF NOT EXISTS dias_no_lectivos (
    fecha TEXT PRIMARY KEY,
    motivo TEXT
);

CREATE TABLE IF NOT EXISTS criterios_actitudinales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS evaluaciones_actitudinales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL REFERENCES estudiantes(id),
    bloque_id INTEGER NOT NULL REFERENCES bloques(id),
    criterio_id INTEGER NOT NULL REFERENCES criterios_actitudinales(id),
    resultado TEXT NOT NULL CHECK(resultado IN ('Si','No')),
    UNIQUE(estudiante_id, bloque_id, criterio_id)
);

CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
