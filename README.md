# Asistencia - Sistema de Control de Jornadas y Liquidación

Sistema para importar marcaciones, calcular jornadas, aplicar overrides y generar liquidación de empleados.

## Instalación

```bash
# Clonar o descargar el proyecto
cd asistencia

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # en Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

## Inicialización

```bash
# Inicializar la base de datos (solo una vez)
python db/init_db.py

# Migración de esquema de liquidación (una vez en bases existentes)
python db/migrate_20260305_liquidacion_detalle.py

# Cargar tarifas de empleados
python db/load_tarifas.py
```

## Uso CLI

### Importar marcaciones desde archivo TXT

```bash
python app.py import data/raw/12-2025.txt
```

### Calcular jornadas

```bash
python app.py jornadas 2025-12-01 2025-12-31
```

### Crear liquidación borrador

```bash
python app.py liquidar 2025 12
```

### Cerrar liquidación

```bash
python app.py cerrar 2025 12
```

## Scripts de utilidad

### Actualizar nombre de empleado

```bash
python db/update_employee_name.py --ac_no 22 --nombre "Veronica"
```

### Añadir tarifa a un empleado

```bash
python db/add_tarifa.py --ac_no 22 --pago 178.61 --nombre "Veronica"
```

### Registrar vale (adelanto)

```bash
python db/add_vale.py --ac_no 22 --monto 2500 --fecha 2026-02-10 --nota "Vale quincena"
```

Notas del sistema de vales:
- El vale se descuenta automáticamente al crear/recalcular la liquidación del mes (`liquidar`).
- Si los vales superan el bruto del mes, el monto final puede quedar negativo.
- Ese excedente también se genera como un nuevo vale ficticio para el primer día del mes siguiente.

### Aplicar overrides en batch

```bash
# Script predefinido (ot.py, ot2.py, ot3.py, ot4.py)
python db/apply_ot_all.py

# Script personalizado con tus datos
python db/apply_ot_custom.py
```

### Exportar liquidación procesada

```bash
python db/export_processed.py 2025 12
```
Genera `data/processed/liquidacion_2025_12.txt` con formato:
```
ID    Nombre        HorasTrabajadas    Monto(antes de vale)    Vales    MontoFinal(luego de vales)
1     Juan          162:06             $26126                  $3000    $23126
2     Ana           120:00             $18000                  $22000   0 ($-4000)
```
También genera `data/processed/liquidacion_2025_12.xlsx` con las mismas columnas.
Los montos se exportan como pesos enteros (sin decimales) y con prefijo `$`.
Si el monto final es negativo, se muestra como `0 ($-valor)` para evitar confusiones.

## UI Streamlit

```bash
streamlit run ui/app.py
```

Accede en navegador: `http://localhost:8501`

Funciones:
- 📅 **Jornadas**: visualizar y editar jornadas con overrides inline
- 🔧 **Overrides**: cargar batch de overrides desde CSV
- 💰 **Liquidación**: crear y ver detalles de liquidación mensual
- ℹ️ **Ayuda**: documentación de uso

## Estructura del proyecto

```
asistencia/
├── app.py                  # CLI principal
├── core/                   # Lógica de negocio
│   ├── parser.py          # Parser de archivos TXT
│   ├── importer.py        # Importar marcaciones a DB
│   ├── jornadas.py        # Calcular jornadas
│   ├── liquidacion.py     # Calcular liquidación
│   ├── overrides.py       # Aplicar correcciones manuales
│   └── logger.py          # Logging centralizado
├── services/               # Casos de uso backend (reutilizable por CLI/API)
│   ├── import_service.py
│   ├── jornadas_service.py
│   ├── liquidacion_service.py
│   └── report_service.py
├── db/                     # Utilidades y scripts de DB
│   ├── database.py        # Conexión SQLite
│   ├── schema.sql         # Esquema de DB
│   ├── init_db.py         # Inicializar DB
│   ├── load_tarifas.py    # Cargar tarifas desde CSV
│   ├── add_tarifa.py      # Añadir tarifa a empleado
│   ├── update_employee_name.py  # Actualizar nombre de empleado
│   ├── apply_ot_all.py    # Aplicar overrides batch (unificado)
│   ├── apply_ot_custom.py # Aplicar overrides personalizados
│   └── export_processed.py # Exportar liquidación procesada
├── data/
│   ├── raw/               # Archivos TXT de importación
│   └── processed/         # Archivos generados de salida (TXT/XLSX)
├── ui/
│   └── app.py            # UI Streamlit
├── tests/
│   └── test_parser.py    # Tests unitarios
├── requirements.txt       # Dependencias Python
├── asistencia.db         # Base de datos SQLite
└── logs/                 # Archivos de log

```

## Base de datos

SQLite: `asistencia.db`

Tablas principales:
- `empleados` — empleados y ac_no
- `tarifas_empleado` — pago/hora por fecha
- `horarios_vigencia` — horario laboral global
- `feriados` — fechas de feriados
- `marcaciones` — entradas y salidas crudas
- `jornadas` — jornadas calculadas
- `jornadas_override` — histórico de correcciones
- `liquidaciones` — liquidaciones mensuales
- `liquidacion_detalle` — desglose por empleado
- `vales` — adelantos entregados por empleado y fecha

## Logging

Los logs se escriben en `logs/asistencia.log` y en stdout. Niveles:
- `INFO`: operaciones normales
- `WARNING`: datos ya importados, empleados sin tarifa
- `ERROR`: fallos en importación, cálculo o liquidación

## Tests

```bash
# Ejecutar todos los tests
pytest tests/

# Ejecutar con output verbose
pytest tests/ -v

# Cobertura
pytest tests/ --cov=core
```

## Notas

- Las horas en `jornadas.entrada_calc` y `jornadas.salida_calc` se almacenan como `HH:MM:SS` (hora sola, sin fecha).
- Los overrides aceptan hora sola (`08:00`) o ISO completo (`2025-12-01T08:00:00`).
- La liquidación usa la tarifa vigente al último día del mes.
- Liquidaciones cerradas no pueden recalcularse (se debe crear una nueva).
- La migración de esquema se ejecuta explícitamente con `db/migrate_20260305_liquidacion_detalle.py`.

## Licencia

(A definir)

---

Para preguntas o reportar bugs, contactar al desarrollador.
