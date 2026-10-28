"""
Sistema de Registro Académico (REGISTRO_MF)
Aplicación web para digitalizar el registro de estudiantes, bloques,
áreas curriculares, actividades de evaluación, calificaciones,
asistencia y evaluación actitudinal, con cálculo automático de
subtotales, totales, promedios y reportes imprimibles.

Ejecutar:
    pip install -r requirements.txt
    python init_db.py
    python app.py
Luego abrir http://127.0.0.1:5000
"""
import os
import re
import sqlite3
from datetime import date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, g
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)
app.secret_key = "cambia-esta-clave-en-produccion-registro-mf"


@app.template_filter("numfmt")
def numfmt(v):
    """Muestra un número sin decimales innecesarios (5.0 -> 5, 4.5 -> 4.5)."""
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return str(int(f)) if f == int(f) else ("%g" % f)


# --------------------------------------------------------------------------
# Conexión a la base de datos
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


# --------------------------------------------------------------------------
# 4.1 Módulo de acceso
# --------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("usuario_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    cfg = {row["clave"]: row["valor"] for row in query("SELECT clave, valor FROM configuracion")}
    return dict(config=cfg, docente_nombre=session.get("nombre"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        contrasena = request.form["contrasena"]
        user = query(
            "SELECT * FROM usuarios WHERE usuario = ? AND estado = 'activo'",
            (usuario,), one=True,
        )
        if user and check_password_hash(user["contrasena"], contrasena):
            session.clear()
            session["usuario_id"] = user["id"]
            session["nombre"] = user["nombre"]
            return redirect(url_for("dashboard"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Configuración / Usuario: cambiar contraseña, nombre del docente, datos
# institucionales del membrete, y acceso a la gestión de áreas.
# --------------------------------------------------------------------------
@app.route("/configuracion", methods=["GET", "POST"])
@login_required
def configuracion():
    if request.method == "POST":
        accion = request.form.get("accion")

        if accion == "datos":
            campos = [
                "nombre_docente", "nombre_directora", "nombre_establecimiento", "ministerio",
                "direccion_departamental", "supervision_educativa",
                "distrito_escolar", "grado", "seccion", "ciclo_escolar",
            ]
            for campo in campos:
                valor = request.form.get(campo, "").strip()
                execute(
                    """INSERT INTO configuracion (clave, valor) VALUES (?,?)
                       ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor""",
                    (campo, valor),
                )
            session["nombre"] = request.form.get("nombre_docente", session.get("nombre"))
            flash("Datos actualizados correctamente.", "success")

        elif accion == "password":
            usuario = query("SELECT * FROM usuarios WHERE id=?", (session["usuario_id"],), one=True)
            actual = request.form.get("actual", "")
            nueva = request.form.get("nueva", "")
            confirmar = request.form.get("confirmar", "")
            if not check_password_hash(usuario["contrasena"], actual):
                flash("La contraseña actual no es correcta.", "error")
            elif len(nueva) < 6:
                flash("La nueva contraseña debe tener al menos 6 caracteres.", "error")
            elif nueva != confirmar:
                flash("La confirmación no coincide con la nueva contraseña.", "error")
            else:
                execute(
                    "UPDATE usuarios SET contrasena=? WHERE id=?",
                    (generate_password_hash(nueva), usuario["id"]),
                )
                flash("Contraseña actualizada correctamente.", "success")

        return redirect(url_for("configuracion"))

    cfg = {row["clave"]: row["valor"] for row in query("SELECT clave, valor FROM configuracion")}
    areas = query("SELECT * FROM areas ORDER BY orden")
    return render_template("configuracion.html", cfg=cfg, areas=areas)


# --------------------------------------------------------------------------
# Panel principal
# --------------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    stats = {
        "estudiantes": query("SELECT COUNT(*) c FROM estudiantes WHERE estado='activo'", one=True)["c"],
        "asistencia_hoy": query(
            "SELECT COUNT(*) c FROM asistencia WHERE fecha = ?", (date.today().isoformat(),), one=True
        )["c"],
        "actividades": query("SELECT COUNT(*) c FROM actividades", one=True)["c"],
        "calificaciones": query("SELECT COUNT(*) c FROM calificaciones", one=True)["c"],
    }
    bloques = query("SELECT * FROM bloques ORDER BY numero")
    return render_template("dashboard.html", stats=stats, bloques=bloques)


# --------------------------------------------------------------------------
# 4.2 Módulo de estudiantes
# --------------------------------------------------------------------------
@app.route("/estudiantes")
@login_required
def estudiantes_lista():
    buscar = request.args.get("q", "").strip()
    if buscar:
        like = f"%{buscar}%"
        estudiantes = query(
            """SELECT * FROM estudiantes
               WHERE (nombres LIKE ? OR apellidos LIKE ? OR clave LIKE ?)
               ORDER BY apellidos, nombres""",
            (like, like, like),
        )
    else:
        estudiantes = query("SELECT * FROM estudiantes ORDER BY apellidos, nombres")
    return render_template("estudiantes.html", estudiantes=estudiantes, buscar=buscar)


@app.route("/estudiantes/nuevo", methods=["GET", "POST"])
@login_required
def estudiante_nuevo():
    if request.method == "POST":
        try:
            execute(
                """INSERT INTO estudiantes (clave, nombres, apellidos, grado, seccion, estado)
                   VALUES (?,?,?,?,?, 'activo')""",
                (request.form["clave"], request.form["nombres"], request.form["apellidos"],
                 request.form["grado"], request.form["seccion"]),
            )
            flash("Estudiante registrado correctamente.", "success")
            return redirect(url_for("estudiantes_lista"))
        except sqlite3.IntegrityError:
            flash("Ya existe un estudiante con esa clave.", "error")
    return render_template("estudiante_form.html", estudiante=None)


@app.route("/estudiantes/<int:id>/editar", methods=["GET", "POST"])
@login_required
def estudiante_editar(id):
    estudiante = query("SELECT * FROM estudiantes WHERE id=?", (id,), one=True)
    if not estudiante:
        flash("Estudiante no encontrado.", "error")
        return redirect(url_for("estudiantes_lista"))
    if request.method == "POST":
        execute(
            """UPDATE estudiantes SET clave=?, nombres=?, apellidos=?, grado=?, seccion=?
               WHERE id=?""",
            (request.form["clave"], request.form["nombres"], request.form["apellidos"],
             request.form["grado"], request.form["seccion"], id),
        )
        flash("Estudiante actualizado.", "success")
        return redirect(url_for("estudiantes_lista"))
    return render_template("estudiante_form.html", estudiante=estudiante)


@app.route("/estudiantes/<int:id>/desactivar")
@login_required
def estudiante_desactivar(id):
    est = query("SELECT estado FROM estudiantes WHERE id=?", (id,), one=True)
    nuevo_estado = "inactivo" if est and est["estado"] == "activo" else "activo"
    execute("UPDATE estudiantes SET estado=? WHERE id=?", (nuevo_estado, id))
    flash("Estado del estudiante actualizado.", "success")
    return redirect(url_for("estudiantes_lista"))


@app.route("/estudiantes/<int:id>/eliminar", methods=["POST"])
@login_required
def estudiante_eliminar(id):
    est = query("SELECT * FROM estudiantes WHERE id=?", (id,), one=True)
    if not est:
        flash("Estudiante no encontrado.", "error")
        return redirect(url_for("estudiantes_lista"))
    # Elimina en cascada sus calificaciones, asistencias y evaluaciones actitudinales
    execute("DELETE FROM calificaciones WHERE estudiante_id=?", (id,))
    execute("DELETE FROM asistencia WHERE estudiante_id=?", (id,))
    execute("DELETE FROM evaluaciones_actitudinales WHERE estudiante_id=?", (id,))
    execute("DELETE FROM estudiantes WHERE id=?", (id,))
    flash(
        f"Se eliminó permanentemente a {est['nombres']} {est['apellidos']}, "
        "junto con sus calificaciones, asistencias y evaluaciones.", "success",
    )
    return redirect(url_for("estudiantes_lista"))


@app.route("/estudiantes/importar", methods=["GET", "POST"])
@login_required
def estudiantes_importar():
    if request.method == "POST":
        texto = request.form.get("datos", "")
        grado = request.form.get("grado", "").strip() or "Segundo"
        seccion = request.form.get("seccion", "").strip() or "A"

        creados, duplicados, invalidas = [], [], []
        for linea in texto.splitlines():
            linea = linea.strip()
            if not linea:
                continue
            partes = [p.strip() for p in linea.split("\t")]
            if len(partes) < 3:
                # Alternativa: separado por comas o por 2+ espacios (pegado sin tabs)
                partes = [p.strip() for p in re.split(r",|\s{2,}", linea) if p.strip()]
            if len(partes) < 3:
                invalidas.append(linea)
                continue
            clave, nombres, apellidos = partes[0], partes[1], partes[2]
            if not clave or not nombres or not apellidos:
                invalidas.append(linea)
                continue
            try:
                execute(
                    """INSERT INTO estudiantes (clave, nombres, apellidos, grado, seccion, estado)
                       VALUES (?,?,?,?,?, 'activo')""",
                    (clave, nombres, apellidos, grado, seccion),
                )
                creados.append(clave)
            except sqlite3.IntegrityError:
                duplicados.append(clave)

        partes_msg = []
        if creados:
            partes_msg.append(f"Se importaron {len(creados)} estudiante(s).")
        if duplicados:
            partes_msg.append(f"Se omitieron {len(duplicados)} clave(s) duplicada(s): {', '.join(duplicados)}.")
        if invalidas:
            partes_msg.append(f"{len(invalidas)} línea(s) no tenían el formato correcto y se omitieron.")
        flash(" ".join(partes_msg) or "No se importó ningún estudiante.", "success" if creados else "error")
        return redirect(url_for("estudiantes_lista"))

    cfg = {row["clave"]: row["valor"] for row in query("SELECT clave, valor FROM configuracion")}
    return render_template("estudiantes_importar.html", cfg=cfg)


# --------------------------------------------------------------------------
# 4.3 Módulo de bloques
# --------------------------------------------------------------------------
@app.route("/bloques", methods=["GET", "POST"])
@login_required
def bloques():
    if request.method == "POST":
        execute(
            "UPDATE bloques SET fecha_inicio=?, fecha_fin=? WHERE id=?",
            (request.form["fecha_inicio"], request.form["fecha_fin"], request.form["bloque_id"]),
        )
        flash("Fechas del bloque actualizadas.", "success")
        return redirect(url_for("bloques"))
    lista = query("SELECT * FROM bloques ORDER BY numero")
    return render_template("bloques.html", bloques=lista)


# --------------------------------------------------------------------------
# 4.7 Módulo de áreas curriculares (accesible desde Configuración, no desde
# el menú principal). El docente puede ver, editar y eliminar áreas/cursos.
# --------------------------------------------------------------------------
@app.route("/areas")
@login_required
def areas():
    lista = query("SELECT * FROM areas ORDER BY orden")
    return render_template("areas.html", areas=lista)


@app.route("/areas/nueva", methods=["POST"])
@login_required
def area_nueva():
    nombre = request.form.get("nombre", "").strip()
    codigo = request.form.get("codigo", "").strip()
    if nombre and codigo:
        try:
            orden = query("SELECT COALESCE(MAX(orden),-1)+1 o FROM areas", one=True)["o"]
            execute(
                "INSERT INTO areas (nombre, codigo, orden, estado) VALUES (?,?,?, 'activo')",
                (nombre, codigo, orden),
            )
            flash("Área/curso agregado correctamente.", "success")
        except sqlite3.IntegrityError:
            flash("Ya existe un área con ese código.", "error")
    else:
        flash("Debes indicar nombre y código del área.", "error")
    return redirect(url_for("areas"))


@app.route("/areas/<int:id>/editar", methods=["POST"])
@login_required
def area_editar(id):
    nombre = request.form.get("nombre", "").strip()
    codigo = request.form.get("codigo", "").strip()
    if nombre and codigo:
        try:
            execute("UPDATE areas SET nombre=?, codigo=? WHERE id=?", (nombre, codigo, id))
            flash("Área/curso actualizado.", "success")
        except sqlite3.IntegrityError:
            flash("Ya existe un área con ese código.", "error")
    return redirect(url_for("areas"))


@app.route("/areas/<int:id>/eliminar", methods=["POST"])
@login_required
def area_eliminar(id):
    # Elimina en cascada las actividades, aspectos y calificaciones asociadas.
    actividades = query("SELECT id FROM actividades WHERE area_id=?", (id,))
    for a in actividades:
        execute(
            "DELETE FROM calificaciones WHERE aspecto_id IN (SELECT id FROM aspectos WHERE actividad_id=?)",
            (a["id"],),
        )
        execute("DELETE FROM aspectos WHERE actividad_id=?", (a["id"],))
    execute("DELETE FROM actividades WHERE area_id=?", (id,))
    execute("DELETE FROM areas WHERE id=?", (id,))
    flash("Área/curso eliminado, junto con sus actividades y calificaciones asociadas.", "success")
    return redirect(url_for("areas"))


# --------------------------------------------------------------------------
# 4.4 Módulo de actividades de evaluación (+ aspectos)
# --------------------------------------------------------------------------
@app.route("/actividades")
@login_required
def actividades_lista():
    bloque_id = request.args.get("bloque_id", type=int)
    area_id = request.args.get("area_id", type=int)

    sql = """SELECT a.*, b.nombre bloque_nombre, b.numero bloque_numero,
                     ar.nombre area_nombre, ar.orden area_orden
              FROM actividades a
              JOIN bloques b ON b.id = a.bloque_id
              JOIN areas ar ON ar.id = a.area_id"""
    conds, params = [], []
    if bloque_id:
        conds.append("a.bloque_id = ?"); params.append(bloque_id)
    if area_id:
        conds.append("a.area_id = ?"); params.append(area_id)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY b.numero, ar.orden, a.fecha_ejecucion IS NULL, a.fecha_ejecucion, a.id"
    actividades = query(sql, params)

    bloques = query("SELECT * FROM bloques ORDER BY numero")
    areas = query("SELECT * FROM areas ORDER BY orden")

    # Agrupa: bloque -> área -> actividades, para que la lista no se vea desordenada
    grupos = []
    for b in bloques:
        if bloque_id and b["id"] != bloque_id:
            continue
        acts_bloque = [a for a in actividades if a["bloque_id"] == b["id"]]
        areas_grupo = []
        vistos = {}
        for a in acts_bloque:
            if a["area_id"] not in vistos:
                vistos[a["area_id"]] = {"area_nombre": a["area_nombre"], "actividades": []}
            vistos[a["area_id"]]["actividades"].append(a)
        areas_grupo = list(vistos.values())
        grupos.append({"bloque": b, "areas": areas_grupo})

    return render_template(
        "actividades.html", grupos=grupos, bloques=bloques, areas=areas,
        bloque_id=bloque_id, area_id=area_id,
    )


@app.route("/actividades/nueva", methods=["GET", "POST"])
@login_required
def actividad_nueva():
    bloques = query("SELECT * FROM bloques ORDER BY numero")
    areas = query("SELECT * FROM areas ORDER BY orden")
    if request.method == "POST":
        nombres_aspecto = request.form.getlist("aspecto_nombre")
        valores_aspecto = request.form.getlist("aspecto_valor")
        valor_total = sum(float(v) for v in valores_aspecto if v.strip())

        actividad_id = execute(
            """INSERT INTO actividades (bloque_id, area_id, nombre, tema, fecha_ejecucion, valor_total)
               VALUES (?,?,?,?,?,?)""",
            (request.form["bloque_id"], request.form["area_id"], request.form["nombre"],
             request.form["tema"], request.form["fecha_ejecucion"], valor_total),
        )
        for i, (nom, val) in enumerate(zip(nombres_aspecto, valores_aspecto)):
            if nom.strip():
                execute(
                    "INSERT INTO aspectos (actividad_id, nombre, valor_maximo, orden) VALUES (?,?,?,?)",
                    (actividad_id, nom.strip(), float(val or 0), i),
                )
        flash("Actividad de evaluación creada.", "success")
        return redirect(url_for("actividad_calificar", id=actividad_id))

    default_bloque_id = request.args.get("bloque_id", type=int)
    default_area_id = request.args.get("area_id", type=int)
    return render_template(
        "actividad_form.html", bloques=bloques, areas=areas,
        default_bloque_id=default_bloque_id, default_area_id=default_area_id,
    )


@app.route("/actividades/<int:id>/eliminar")
@login_required
def actividad_eliminar(id):
    execute("DELETE FROM actividades WHERE id=?", (id,))
    flash("Actividad eliminada.", "success")
    return redirect(url_for("actividades_lista"))


@app.route("/actividades/<int:id>/editar", methods=["GET", "POST"])
@login_required
def actividad_editar(id):
    actividad = query(
        """SELECT a.*, b.nombre bloque_nombre, ar.nombre area_nombre
           FROM actividades a JOIN bloques b ON b.id=a.bloque_id JOIN areas ar ON ar.id=a.area_id
           WHERE a.id=?""", (id,), one=True,
    )
    if not actividad:
        flash("Actividad no encontrada.", "error")
        return redirect(url_for("actividades_lista"))

    if request.method == "POST":
        execute(
            "UPDATE actividades SET nombre=?, tema=?, fecha_ejecucion=? WHERE id=?",
            (request.form["nombre"], request.form["tema"], request.form["fecha_ejecucion"], id),
        )
        # Actualiza el nombre/valor de cada aspecto existente (sin borrar calificaciones)
        aspecto_ids = request.form.getlist("aspecto_id")
        aspecto_nombres = request.form.getlist("aspecto_nombre")
        aspecto_valores = request.form.getlist("aspecto_valor")
        for aid, nom, val in zip(aspecto_ids, aspecto_nombres, aspecto_valores):
            execute(
                "UPDATE aspectos SET nombre=?, valor_maximo=? WHERE id=?",
                (nom.strip(), float(val or 0), aid),
            )
        nuevo_total = query(
            "SELECT COALESCE(SUM(valor_maximo),0) t FROM aspectos WHERE actividad_id=?", (id,), one=True
        )["t"]
        execute("UPDATE actividades SET valor_total=? WHERE id=?", (nuevo_total, id))

        flash("Actividad actualizada.", "success")
        return redirect(url_for("actividades_lista", bloque_id=actividad["bloque_id"]))

    aspectos = query("SELECT * FROM aspectos WHERE actividad_id=? ORDER BY orden", (id,))
    return render_template("actividad_editar.html", actividad=actividad, aspectos=aspectos)


@app.route("/actividades/plantilla", methods=["GET", "POST"])
@login_required
def actividad_plantilla():
    bloques = query("SELECT * FROM bloques ORDER BY numero")
    areas = query("SELECT * FROM areas ORDER BY orden")

    ASPECTOS_DEFECTO = ["Producción", "Proceso", "Cantidad", "Limpieza"]

    if request.method == "POST":
        bloque_id = int(request.form["bloque_id"])
        area_sel = request.form["area_id"]  # "all" o el id de un área específica

        if area_sel == "all":
            areas_objetivo = areas
        else:
            areas_objetivo = [a for a in areas if a["id"] == int(area_sel)]

        creadas, omitidas = [], []
        for area in areas_objetivo:
            existentes = query(
                "SELECT COUNT(*) c FROM actividades WHERE bloque_id=? AND area_id=?",
                (bloque_id, area["id"]), one=True,
            )["c"]
            if existentes > 0:
                omitidas.append(area["nombre"])
                continue

            # 4 actividades regulares con los 4 aspectos predeterminados (5 pts c/u = 20 pts)
            for i in range(1, 5):
                act_id = execute(
                    """INSERT INTO actividades (bloque_id, area_id, nombre, tema, fecha_ejecucion, valor_total)
                       VALUES (?,?,?,?,?,?)""",
                    (bloque_id, area["id"], f"Actividad {i}", "", None, 20),
                )
                for j, nom_aspecto in enumerate(ASPECTOS_DEFECTO):
                    execute(
                        "INSERT INTO aspectos (actividad_id, nombre, valor_maximo, orden) VALUES (?,?,?,?)",
                        (act_id, nom_aspecto, 5, j),
                    )

            # 5ta actividad: evaluación / examen, con una sola nota de 20 pts
            act_id = execute(
                """INSERT INTO actividades (bloque_id, area_id, nombre, tema, fecha_ejecucion, valor_total)
                   VALUES (?,?,?,?,?,?)""",
                (bloque_id, area["id"], "Evaluación", "", None, 20),
            )
            execute(
                "INSERT INTO aspectos (actividad_id, nombre, valor_maximo, orden) VALUES (?,?,?,?)",
                (act_id, "Nota", 20, 0),
            )
            creadas.append(area["nombre"])

        if creadas:
            msg = f"Se generaron las actividades predeterminadas (100 pts) para: {', '.join(creadas)}."
            if omitidas:
                msg += f" Se omitieron (ya tenían actividades): {', '.join(omitidas)}."
            flash(msg, "success")
        else:
            flash(
                "No se generó nada: todas las áreas seleccionadas ya tenían actividades en ese bloque.",
                "error",
            )
        return redirect(url_for("actividades_lista", bloque_id=bloque_id))

    default_bloque_id = request.args.get("bloque_id", type=int)
    default_area_id = request.args.get("area_id", type=int)
    return render_template(
        "actividad_plantilla.html", bloques=bloques, areas=areas,
        default_bloque_id=default_bloque_id, default_area_id=default_area_id,
    )


# --------------------------------------------------------------------------
# 4.5 Módulo de calificaciones (registro por actividad)
# --------------------------------------------------------------------------
@app.route("/actividades/<int:id>/calificar", methods=["GET", "POST"])
@login_required
def actividad_calificar(id):
    actividad = query(
        """SELECT a.*, b.nombre bloque_nombre, ar.nombre area_nombre
           FROM actividades a JOIN bloques b ON b.id=a.bloque_id JOIN areas ar ON ar.id=a.area_id
           WHERE a.id=?""", (id,), one=True,
    )
    if not actividad:
        flash("Actividad no encontrada.", "error")
        return redirect(url_for("actividades_lista"))

    aspectos = query("SELECT * FROM aspectos WHERE actividad_id=? ORDER BY orden", (id,))
    estudiantes = query(
        "SELECT * FROM estudiantes WHERE estado='activo' ORDER BY apellidos, nombres"
    )

    if request.method == "POST":
        for est in estudiantes:
            for asp in aspectos:
                campo = f"cal_{est['id']}_{asp['id']}"
                valor = request.form.get(campo, "").strip()
                valor = float(valor) if valor else 0
                execute(
                    """INSERT INTO calificaciones (estudiante_id, aspecto_id, calificacion)
                       VALUES (?,?,?)
                       ON CONFLICT(estudiante_id, aspecto_id)
                       DO UPDATE SET calificacion=excluded.calificacion""",
                    (est["id"], asp["id"], valor),
                )
        flash("Calificaciones guardadas.", "success")
        return redirect(url_for("actividad_calificar", id=id))

    # Construir matriz estudiante -> {aspecto_id: calificacion}
    notas = query(
        """SELECT c.estudiante_id, c.aspecto_id, c.calificacion FROM calificaciones c
           JOIN aspectos a ON a.id = c.aspecto_id WHERE a.actividad_id=?""", (id,),
    )
    matriz = {}
    for n in notas:
        matriz.setdefault(n["estudiante_id"], {})[n["aspecto_id"]] = n["calificacion"]

    filas = []
    for est in estudiantes:
        valores = {asp["id"]: matriz.get(est["id"], {}).get(asp["id"], "") for asp in aspectos}
        subtotal = sum(v for v in valores.values() if isinstance(v, (int, float)))
        filas.append({"estudiante": est, "valores": valores, "subtotal": subtotal})

    return render_template(
        "calificaciones.html", actividad=actividad, aspectos=aspectos, filas=filas
    )


# --------------------------------------------------------------------------
# 4.6 Módulo de asistencia
# --------------------------------------------------------------------------
DIAS_SEMANA_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


@app.route("/asistencia", methods=["GET", "POST"])
@login_required
def asistencia():
    fecha = request.args.get("fecha") or date.today().isoformat()
    estudiantes = query(
        "SELECT * FROM estudiantes WHERE estado='activo' ORDER BY apellidos, nombres"
    )

    if request.method == "POST":
        fecha = request.form["fecha"]
        if request.form.get("no_hubo_clases") == "on":
            motivo = request.form.get("motivo", "").strip() or "No hubo clases"
            execute(
                """INSERT INTO dias_no_lectivos (fecha, motivo) VALUES (?,?)
                   ON CONFLICT(fecha) DO UPDATE SET motivo=excluded.motivo""",
                (fecha, motivo),
            )
            execute("DELETE FROM asistencia WHERE fecha=?", (fecha,))
            flash(f"Se marcó el {fecha} como día sin clases ({motivo}).", "success")
        else:
            execute("DELETE FROM dias_no_lectivos WHERE fecha=?", (fecha,))
            for est in estudiantes:
                estado = request.form.get(f"estado_{est['id']}", "Presente")
                execute(
                    """INSERT INTO asistencia (estudiante_id, fecha, estado) VALUES (?,?,?)
                       ON CONFLICT(estudiante_id, fecha) DO UPDATE SET estado=excluded.estado""",
                    (est["id"], fecha, estado),
                )
            flash("Asistencia registrada.", "success")
        return redirect(url_for("asistencia", fecha=fecha))

    registros = query("SELECT estudiante_id, estado FROM asistencia WHERE fecha=?", (fecha,))
    estados = {r["estudiante_id"]: r["estado"] for r in registros}
    dia_no_lectivo = query("SELECT * FROM dias_no_lectivos WHERE fecha=?", (fecha,), one=True)
    return render_template(
        "asistencia.html", estudiantes=estudiantes, fecha=fecha, estados=estados,
        dia_no_lectivo=dia_no_lectivo,
    )


@app.route("/asistencia/eliminar", methods=["POST"])
@login_required
def asistencia_eliminar():
    fecha = request.form["fecha"]
    execute("DELETE FROM asistencia WHERE fecha=?", (fecha,))
    execute("DELETE FROM dias_no_lectivos WHERE fecha=?", (fecha,))
    flash(f"Se eliminó el registro de asistencia del {fecha}.", "success")
    return redirect(url_for("asistencia", fecha=fecha))


@app.route("/asistencia/resumen")
@login_required
def asistencia_resumen():
    resumen = query(
        """SELECT e.id, e.nombres, e.apellidos,
                  SUM(CASE WHEN a.estado='Presente' THEN 1 ELSE 0 END) presentes,
                  SUM(CASE WHEN a.estado='Ausente' THEN 1 ELSE 0 END) ausentes,
                  SUM(CASE WHEN a.estado='Justificado' THEN 1 ELSE 0 END) justificados,
                  COUNT(a.id) total
           FROM estudiantes e
           LEFT JOIN asistencia a ON a.estudiante_id = e.id
           WHERE e.estado='activo'
           GROUP BY e.id ORDER BY e.apellidos, e.nombres"""
    )
    dias_no_lectivos = query("SELECT * FROM dias_no_lectivos ORDER BY fecha DESC")
    return render_template("asistencia_resumen.html", resumen=resumen, dias_no_lectivos=dias_no_lectivos)


@app.route("/asistencia/detalle/<int:estudiante_id>")
@login_required
def asistencia_detalle(estudiante_id):
    estudiante = query("SELECT * FROM estudiantes WHERE id=?", (estudiante_id,), one=True)
    if not estudiante:
        flash("Estudiante no encontrado.", "error")
        return redirect(url_for("asistencia_resumen"))

    registros = query(
        "SELECT fecha, estado FROM asistencia WHERE estudiante_id=? ORDER BY fecha",
        (estudiante_id,),
    )
    detalle = []
    for r in registros:
        try:
            d = date.fromisoformat(r["fecha"])
            dia_semana = DIAS_SEMANA_ES[d.weekday()]
        except ValueError:
            dia_semana = "—"
        detalle.append({"fecha": r["fecha"], "dia_semana": dia_semana, "estado": r["estado"]})

    return render_template("asistencia_detalle.html", estudiante=estudiante, detalle=detalle)


# --------------------------------------------------------------------------
# 4.8 Módulo de evaluación actitudinal
# --------------------------------------------------------------------------
@app.route("/actitudinal", methods=["GET", "POST"])
@login_required
def actitudinal():
    bloque_id = request.args.get("bloque_id", type=int) or query(
        "SELECT id FROM bloques ORDER BY numero LIMIT 1", one=True
    )["id"]
    bloques = query("SELECT * FROM bloques ORDER BY numero")
    criterios = query("SELECT * FROM criterios_actitudinales ORDER BY orden")
    estudiantes = query(
        "SELECT * FROM estudiantes WHERE estado='activo' ORDER BY apellidos, nombres"
    )

    if request.method == "POST":
        bloque_id = int(request.form["bloque_id"])
        for est in estudiantes:
            for crit in criterios:
                campo = f"crit_{est['id']}_{crit['id']}"
                resultado = request.form.get(campo, "No")
                execute(
                    """INSERT INTO evaluaciones_actitudinales
                       (estudiante_id, bloque_id, criterio_id, resultado) VALUES (?,?,?,?)
                       ON CONFLICT(estudiante_id, bloque_id, criterio_id)
                       DO UPDATE SET resultado=excluded.resultado""",
                    (est["id"], bloque_id, crit["id"], resultado),
                )
        flash("Evaluación actitudinal guardada.", "success")
        return redirect(url_for("actitudinal", bloque_id=bloque_id))

    registros = query(
        "SELECT estudiante_id, criterio_id, resultado FROM evaluaciones_actitudinales WHERE bloque_id=?",
        (bloque_id,),
    )
    matriz = {}
    for r in registros:
        matriz.setdefault(r["estudiante_id"], {})[r["criterio_id"]] = r["resultado"]

    return render_template(
        "actitudinal.html", bloques=bloques, bloque_id=bloque_id, criterios=criterios,
        estudiantes=estudiantes, matriz=matriz,
    )


# --------------------------------------------------------------------------
# Utilidad: subtotal de una actividad para un estudiante
# --------------------------------------------------------------------------
def subtotal_actividad(estudiante_id, actividad_id):
    row = query(
        """SELECT COALESCE(SUM(c.calificacion),0) total FROM calificaciones c
           JOIN aspectos a ON a.id=c.aspecto_id WHERE a.actividad_id=? AND c.estudiante_id=?""",
        (actividad_id, estudiante_id), one=True,
    )
    return row["total"] if row else 0


# --------------------------------------------------------------------------
# 4.9 Índice de reportes
# --------------------------------------------------------------------------
@app.route("/reportes")
@login_required
def reportes_index():
    estudiantes = query("SELECT * FROM estudiantes WHERE estado='activo' ORDER BY apellidos, nombres")
    bloques = query("SELECT * FROM bloques ORDER BY numero")
    areas = query("SELECT * FROM areas ORDER BY orden")
    return render_template(
        "reportes.html", estudiantes=estudiantes, bloques=bloques, areas=areas
    )


# --------------------------------------------------------------------------
# Reporte oficial de calificaciones por área y bloque: replica el formato
# físico del Ministerio de Educación (todas las actividades del área en un
# bloque, con subtotal por actividad y total sobre la suma de sus valores).
# --------------------------------------------------------------------------
@app.route("/reportes/area_bloque")
@login_required
def reporte_area_bloque():
    areas = query("SELECT * FROM areas ORDER BY orden")
    bloques = query("SELECT * FROM bloques ORDER BY numero")
    if not areas or not bloques:
        flash("Debes tener al menos un área y un bloque configurados.", "error")
        return redirect(url_for("reportes_index"))

    area_id = request.args.get("area_id", type=int) or areas[0]["id"]
    bloque_id = request.args.get("bloque_id", type=int) or bloques[0]["id"]
    area = next((a for a in areas if a["id"] == area_id), areas[0])
    bloque = next((b for b in bloques if b["id"] == bloque_id), bloques[0])

    actividades = query(
        """SELECT * FROM actividades WHERE area_id=? AND bloque_id=?
           ORDER BY fecha_ejecucion IS NULL, fecha_ejecucion, id""",
        (area_id, bloque_id),
    )
    actividades_con_aspectos = []
    total_maximo = 0
    for a in actividades:
        aspectos = query("SELECT * FROM aspectos WHERE actividad_id=? ORDER BY orden", (a["id"],))
        actividades_con_aspectos.append({"actividad": a, "aspectos": aspectos})
        total_maximo += a["valor_total"]

    estudiantes = query("SELECT * FROM estudiantes WHERE estado='activo' ORDER BY apellidos, nombres")

    # Matriz completa: calificacion por estudiante y por aspecto
    notas = query(
        """SELECT c.estudiante_id, c.aspecto_id, c.calificacion FROM calificaciones c
           JOIN aspectos asp ON asp.id = c.aspecto_id
           JOIN actividades act ON act.id = asp.actividad_id
           WHERE act.area_id=? AND act.bloque_id=?""",
        (area_id, bloque_id),
    )
    matriz = {}
    for n in notas:
        matriz.setdefault(n["estudiante_id"], {})[n["aspecto_id"]] = n["calificacion"]

    filas = []
    for est in estudiantes:
        grupos_actividad = []
        total_estudiante = 0
        for grupo in actividades_con_aspectos:
            valores = [matriz.get(est["id"], {}).get(asp["id"], "") for asp in grupo["aspectos"]]
            subtotal = sum(v for v in valores if isinstance(v, (int, float)))
            total_estudiante += subtotal
            grupos_actividad.append({"valores": valores, "subtotal": subtotal})
        filas.append({"estudiante": est, "grupos": grupos_actividad, "total": total_estudiante})

    return render_template(
        "reporte_area_bloque.html", areas=areas, bloques=bloques, area=area, bloque=bloque,
        actividades_con_aspectos=actividades_con_aspectos, filas=filas, total_maximo=total_maximo,
    )


# --------------------------------------------------------------------------
# 4.10 Reporte de calificaciones por bloque (por área, los 4 bloques + promedio)
# --------------------------------------------------------------------------
@app.route("/reportes/bloque/<int:estudiante_id>")
@login_required
def reporte_bloque(estudiante_id):
    estudiante = query("SELECT * FROM estudiantes WHERE id=?", (estudiante_id,), one=True)
    areas = query("SELECT * FROM areas ORDER BY orden")
    bloques = query("SELECT * FROM bloques ORDER BY numero")

    actividades = query(
        "SELECT id, area_id, bloque_id FROM actividades"
    )

    tabla = []
    for area in areas:
        fila = {"area": area, "bloques": {}, "valores": []}
        for bloque in bloques:
            acts = [a for a in actividades if a["area_id"] == area["id"] and a["bloque_id"] == bloque["id"]]
            if not acts:
                fila["bloques"][bloque["id"]] = None
                continue
            total = sum(subtotal_actividad(estudiante_id, a["id"]) for a in acts)
            fila["bloques"][bloque["id"]] = total
            fila["valores"].append(total)
        fila["promedio"] = round(sum(fila["valores"]) / len(fila["valores"]), 1) if fila["valores"] else None
        tabla.append(fila)

    return render_template(
        "reporte_bloque.html", estudiante=estudiante, areas=areas, bloques=bloques, tabla=tabla
    )


# --------------------------------------------------------------------------
# 4.11 Reporte final consolidado por estudiante
# --------------------------------------------------------------------------
@app.route("/reportes/final/<int:estudiante_id>")
@login_required
def reporte_final(estudiante_id):
    estudiante = query("SELECT * FROM estudiantes WHERE id=?", (estudiante_id,), one=True)
    areas = query("SELECT * FROM areas ORDER BY orden")
    bloques = query("SELECT * FROM bloques ORDER BY numero")
    criterios = query("SELECT * FROM criterios_actitudinales ORDER BY orden")

    actividades = query("SELECT id, area_id, bloque_id FROM actividades")

    tabla = []
    for area in areas:
        fila = {"area": area, "bloques": {}, "valores": []}
        for bloque in bloques:
            acts = [a for a in actividades if a["area_id"] == area["id"] and a["bloque_id"] == bloque["id"]]
            if not acts:
                fila["bloques"][bloque["id"]] = None
                continue
            total = sum(subtotal_actividad(estudiante_id, a["id"]) for a in acts)
            fila["bloques"][bloque["id"]] = total
            fila["valores"].append(total)
        fila["promedio"] = round(sum(fila["valores"]) / len(fila["valores"]), 1) if fila["valores"] else None
        tabla.append(fila)

    actitud = query(
        """SELECT criterio_id, bloque_id, resultado FROM evaluaciones_actitudinales
           WHERE estudiante_id=?""", (estudiante_id,),
    )
    matriz_actitud = {}
    for r in actitud:
        matriz_actitud.setdefault(r["criterio_id"], {})[r["bloque_id"]] = r["resultado"]

    todos_estudiantes = query("SELECT * FROM estudiantes WHERE estado='activo' ORDER BY apellidos, nombres")

    return render_template(
        "reporte_final.html", estudiante=estudiante, areas=areas, bloques=bloques,
        tabla=tabla, criterios=criterios, matriz_actitud=matriz_actitud,
        todos_estudiantes=todos_estudiantes,
    )


# --------------------------------------------------------------------------
# Reportes por grupo (todos los estudiantes registrados en una sola tabla)
# --------------------------------------------------------------------------
@app.route("/reportes/grupal/bloque")
@login_required
def reporte_grupal_bloque():
    bloques = query("SELECT * FROM bloques ORDER BY numero")
    bloque_id = request.args.get("bloque_id", type=int) or bloques[0]["id"]
    areas = query("SELECT * FROM areas ORDER BY orden")
    estudiantes = query("SELECT * FROM estudiantes WHERE estado='activo' ORDER BY apellidos, nombres")
    actividades = query("SELECT id, area_id FROM actividades WHERE bloque_id=?", (bloque_id,))

    filas = []
    for est in estudiantes:
        valores = {}
        for area in areas:
            acts = [a for a in actividades if a["area_id"] == area["id"]]
            valores[area["id"]] = sum(subtotal_actividad(est["id"], a["id"]) for a in acts) if acts else None
        numeros = [v for v in valores.values() if v is not None]
        promedio = round(sum(numeros) / len(numeros), 1) if numeros else None
        filas.append({"estudiante": est, "valores": valores, "promedio": promedio})

    bloque_actual = next(b for b in bloques if b["id"] == bloque_id)
    return render_template(
        "reporte_grupal_bloque.html", bloques=bloques, bloque_id=bloque_id,
        bloque_actual=bloque_actual, areas=areas, filas=filas,
    )


@app.route("/reportes/grupal/final")
@login_required
def reporte_grupal_final():
    areas = query("SELECT * FROM areas ORDER BY orden")
    bloques = query("SELECT * FROM bloques ORDER BY numero")
    estudiantes = query("SELECT * FROM estudiantes WHERE estado='activo' ORDER BY apellidos, nombres")
    actividades = query("SELECT id, area_id, bloque_id FROM actividades")

    filas = []
    for est in estudiantes:
        valores = {}
        for area in areas:
            parciales = []
            for bloque in bloques:
                acts = [a for a in actividades if a["area_id"] == area["id"] and a["bloque_id"] == bloque["id"]]
                if acts:
                    parciales.append(sum(subtotal_actividad(est["id"], a["id"]) for a in acts))
            valores[area["id"]] = round(sum(parciales) / len(parciales), 1) if parciales else None
        numeros = [v for v in valores.values() if v is not None]
        promedio_general = round(sum(numeros) / len(numeros), 1) if numeros else None
        filas.append({"estudiante": est, "valores": valores, "promedio_general": promedio_general})

    return render_template("reporte_grupal_final.html", areas=areas, filas=filas)


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        import init_db
        init_db.main()
    app.run(debug=True)
