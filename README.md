# Sistema de Gestión Académica (REGISTRO_MF)

Aplicación web para digitalizar el registro académico del docente: estudiantes,
bloques, áreas curriculares, actividades de evaluación, calificaciones,
asistencia, evaluación actitudinal y reportes imprimibles — con cálculo
automático de subtotales, totales y promedios.

Generada a partir del documento técnico `REGISTRO_MF.docx`, siguiendo la
arquitectura web sencilla propuesta en la sección 3 del documento:
navegador → interfaz → lógica de aplicación (módulos) → base de datos.

## Tecnología

- **Backend:** Python 3 + Flask
- **Base de datos:** SQLite (archivo único `database.db`, sin necesidad de instalar un motor aparte)
- **Frontend:** HTML + CSS propio (sin dependencias externas), listo para imprimir

## Instalación y ejecución

```bash
# 1. Crear un entorno virtual (recomendado)
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Inicializar la base de datos (crea bloques, áreas, criterios y usuario docente)
python init_db.py

# 4. Ejecutar la aplicación
python app.py
```

Luego abre el navegador en **http://127.0.0.1:5000**

### Usuario por defecto

- **Usuario:** `docente`
- **Contraseña:** `docente123`

Cámbiala editando la tabla `usuarios` o pídeme que agregue una pantalla de
cambio de contraseña.

## Módulos incluidos

| Módulo | Descripción |
|---|---|
| Acceso | Inicio/cierre de sesión, protección de rutas |
| Estudiantes | Registrar, editar, buscar, activar/desactivar o **eliminar permanentemente**; **importar en bloque pegando datos copiados de Excel** (clave, nombres, apellidos) |
| Bloques | Los 4 bloques del ciclo académico, con fechas configurables |
| Actividades de evaluación | Vista **agrupada por bloque** mostrando todas las actividades; crear actividad con aspectos a calificar (valor configurable), el valor total se calcula solo |
| Calificaciones | Matriz estudiante × aspecto, con subtotal automático (suma de aspectos) |
| Asistencia | Registro diario Presente / Ausente / Justificado, con resumen general y **opción de eliminar el registro de un día** si el docente se equivocó |
| Evaluación actitudinal | Criterios Sí/No por bloque, por estudiante |
| Reportes | **Cuadro de calificaciones** por área y bloque (replica el formato físico del MINEDUC: todas las actividades del área en columnas, subtotal por actividad, total sobre 100, encabezado repetido si ocupa varias hojas); **Boleta de Calificaciones** por alumno (tarjeta plegada de 2 hojas, igual a la tarjeta física); reportes **por grupo** (cuadro grupal de un bloque y reporte final de todo el grupo) |
| Configuración (⚙ junto al nombre del docente) | Cambiar nombre del docente, **nombre de la directora**, grado/sección, **ciclo escolar** y los datos del membrete institucional; cambiar contraseña; **gestión de áreas/cursos** (agregar, editar o eliminar, con advertencia porque elimina también sus actividades y calificaciones) |

### Boleta de Calificaciones (tarjeta plegada)

Replica exactamente la tarjeta física de doble hoja que usa la escuela:

- **Hoja 1**: mitad izquierda en blanco (el reverso de la tarjeta al doblarla) y
  mitad derecha con el logo de la escuela, el título, la clave, el nombre del
  estudiante, el nombre del docente, el grado y el ciclo escolar.
- **Hoja 2**: mitad izquierda con el cuadro de las 9 áreas × 4 bloques + promedio
  (si un área no tiene nota en un bloque, esa celda queda en blanco) y mitad
  derecha con la evaluación actitudinal (SI/NO por bloque), las firmas de
  docente/directora y la tabla de firma del padre/madre/encargado por bloque.

Se accede desde **Reportes → Boleta de Calificaciones**, eligiendo el estudiante
en la parte superior.

**Imágenes de la portada**: coloca estos dos archivos, con estos nombres exactos,
en la carpeta `static/img/` del proyecto (ya viene creada, con instrucciones
dentro):
- `LogEsc.png` — el escudo/logo de la escuela
- `Boys.jpg` — la ilustración de los niños

No hace falta tocar ningún código: en cuanto los archivos estén ahí, aparecen
automáticamente en la portada de la boleta. Si falta alguno, esa zona simplemente
queda en blanco.

### Plantilla predeterminada de actividades

Desde **Actividades → "+ Generar plantilla"**, el sistema crea de una
vez la estructura típica de un bloque para un área (como se ve en el registro físico):

- 4 actividades con los aspectos **Producción, Proceso, Cantidad y Limpieza**
  (5 puntos cada uno = 20 pts por actividad, editable después)
- 1 actividad "Evaluación" con una sola nota de 20 pts
- **Total del bloque: 100 puntos**

Puedes generarla para **un área específica** o para **todas las áreas a la vez**
(crea las 5 actividades en cada una). Si un área ya tiene actividades en ese
bloque, se omite para evitar duplicados.

Luego edita cada actividad ("Editar") para poner el tema real, la fecha de ejecución
y, si hace falta, renombrar o cambiar el valor de cada aspecto.

La lista de **Actividades** ahora se agrupa por bloque y, dentro de cada bloque,
por área, con filtros independientes para no perderte entre muchas actividades.

### Asistencia: días sin clases y detalle por estudiante

- Al tomar asistencia puedes marcar el día como **"No hubo clases"** (feriado,
  actividad institucional, etc.) indicando el motivo; ese día no se contabiliza
  para ningún estudiante y queda registrado en el resumen general.
- Desde **Asistencia → Ver resumen general → Ver detalle** por estudiante puedes
  ver la lista completa de fechas en que asistió, con el día de la semana y el
  estado (Presente/Ausente/Justificado).

### Membrete de impresión

Todos los reportes se imprimen en **orientación horizontal** con el membrete:

```
        MINISTERIO DE EDUCACIÓN
   DIRECCIÓN DEPARTAMENTAL DE EDUCACIÓN
        SUPERVISIÓN EDUCATIVA
     DISTRITO ESCOLAR No. 07-01-04

ESCUELA OFICIAL RURAL MIXTA: ...   (subrayado, alineado a la izquierda)

MAESTRO(A): ...                    GRADO Y SECCIÓN: ...
UNIDAD: ...                        ÁREA: ...
```

Estos datos (nombre del docente, del establecimiento, distrito escolar, etc.)
se editan desde **Configuración**, sin tocar el código.

Los logotipos (Gobierno de Guatemala e izquierda del MINEDUC) se cargan desde
las URL oficiales que compartiste; se necesita conexión a internet al momento
de imprimir para que aparezcan. Si prefieres que funcionen sin internet,
descarga esas dos imágenes a `static/img/` y cambia las rutas `src="https://..."`
por `src="{{ url_for('static', filename='img/logo1.png') }}"` en
`templates/_print_header.html`.

## Estructura del proyecto

```
registro_mf/
├── app.py                 # Rutas y lógica de negocio (todos los módulos)
├── init_db.py              # Crea la base de datos y carga datos semilla
├── schema.sql               # Esquema de la base de datos
├── requirements.txt
├── database.db              # Se genera al ejecutar init_db.py (no incluido)
├── static/
│   └── style.css
└── templates/
    ├── base.html, login.html, dashboard.html
    ├── estudiantes.html, estudiante_form.html, estudiantes_importar.html
    ├── bloques.html, areas.html
    ├── actividades.html, actividad_form.html, actividad_editar.html,
    │   actividad_plantilla.html, calificaciones.html
    ├── asistencia.html, asistencia_resumen.html, asistencia_detalle.html
    ├── actitudinal.html
    ├── configuracion.html
    ├── _print_header.html          # membrete institucional reutilizable (con logotipos)
    └── reportes.html, reporte_area_bloque.html, reporte_bloque.html,
        reporte_final.html          # ← Boleta de Calificaciones (tarjeta plegada)
        reporte_grupal_bloque.html, reporte_grupal_final.html
static/img/                          # coloca aquí LogEsc.png y Boys.jpg
```

> Si ya tenías una base de datos generada con la versión anterior (columna
> `codigo` en vez de `clave`), simplemente vuelve a ejecutar `python init_db.py`:
> migra la columna automáticamente sin perder datos.

## Cómo se calcula cada valor (sección 7 del documento)

```
Subtotal (por actividad) = suma de las calificaciones de cada aspecto
Promedio (por área)      = promedio de los subtotales de bloque disponibles
```

## Personalización rápida

- **Nombre del establecimiento / docente:** tabla `configuracion` en la base de datos
  (o edítalo directamente con cualquier gestor SQLite).
- **Áreas o criterios actitudinales distintos:** edítalos en `init_db.py` antes de
  ejecutarlo por primera vez, o directamente en las tablas `areas` /
  `criterios_actitudinales`.

## Próximos pasos sugeridos

- Exportar los reportes a PDF (actualmente se imprimen desde el navegador,
  vía Ctrl+P, con un formato ya preparado para impresión).
- Pantalla para cambiar la contraseña del docente.
- Soporte para más de un grado/sección o más de un docente.

Si quieres que agregue alguna de estas mejoras, o que adapte el sistema a un
grado/sección específico, dímelo y lo ajusto.
