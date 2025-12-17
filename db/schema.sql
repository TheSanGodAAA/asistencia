PRAGMA foreign_keys = ON;

-- =========
-- Empleados
-- =========
CREATE TABLE IF NOT EXISTS empleados (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ac_no     INTEGER NOT NULL UNIQUE,
  nombre    TEXT    NOT NULL,
  activo    INTEGER NOT NULL DEFAULT 1
);

-- ===========================
-- Tarifas (pago/hora) vigencia
-- pago_hora_cent: UYU * 100
-- ===========================
CREATE TABLE IF NOT EXISTS tarifas_empleado (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  empleado_id     INTEGER NOT NULL,
  desde           TEXT    NOT NULL, -- YYYY-MM-DD
  pago_hora_cent  INTEGER NOT NULL,
  nota            TEXT,
  FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tarifas_empleado_desde
  ON tarifas_empleado(empleado_id, desde);

-- =======================
-- Horarios globales vigencia
-- (08:00 - 17:30, etc.)
-- =======================
CREATE TABLE IF NOT EXISTS horarios_vigencia (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  desde          TEXT    NOT NULL UNIQUE, -- YYYY-MM-DD
  hora_inicio    TEXT    NOT NULL,        -- HH:MM
  hora_fin       TEXT    NOT NULL,        -- HH:MM
  tolerancia_min INTEGER NOT NULL DEFAULT 5,
  nota           TEXT
);

-- =========
-- Feriados
-- =========
CREATE TABLE IF NOT EXISTS feriados (
  fecha      TEXT PRIMARY KEY,  -- YYYY-MM-DD
  nombre     TEXT NOT NULL,
  horas_pagas INTEGER NOT NULL DEFAULT 8
);

-- =========
-- Imports
-- =========
CREATE TABLE IF NOT EXISTS imports (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  archivo_nombre TEXT NOT NULL,
  hash         TEXT UNIQUE,
  importado_en TEXT NOT NULL  -- ISO timestamp
);

-- ==================
-- Marcaciones (crudo)
-- ==================
CREATE TABLE IF NOT EXISTS marcaciones (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  empleado_id INTEGER NOT NULL,
  ts          TEXT    NOT NULL, -- ISO timestamp
  tipo        TEXT    NOT NULL CHECK(tipo IN ('ENT','SAL')),
  import_id   INTEGER,
  raw_line    TEXT,
  FOREIGN KEY (empleado_id) REFERENCES empleados(id),
  FOREIGN KEY (import_id) REFERENCES imports(id)
);

CREATE INDEX IF NOT EXISTS idx_marcaciones_emp_ts
  ON marcaciones(empleado_id, ts);

-- ==================
-- Jornadas (calculado)
-- ==================
CREATE TABLE IF NOT EXISTS jornadas (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  empleado_id  INTEGER NOT NULL,
  fecha        TEXT    NOT NULL, -- YYYY-MM-DD
  entrada_calc TEXT,             -- ISO timestamp nullable
  salida_calc  TEXT,             -- ISO timestamp nullable
  minutos_calc INTEGER,          -- nullable
  estado       TEXT    NOT NULL,
  detalle      TEXT,
  FOREIGN KEY (empleado_id) REFERENCES empleados(id),
  UNIQUE (empleado_id, fecha)
);

-- =======================
-- Overrides (manual, audita)
-- =======================
CREATE TABLE IF NOT EXISTS jornadas_override (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  jornada_id    INTEGER NOT NULL,
  entrada_manual TEXT,
  salida_manual  TEXT,
  motivo        TEXT NOT NULL,
  creado_en     TEXT NOT NULL, -- ISO timestamp
  FOREIGN KEY (jornada_id) REFERENCES jornadas(id) ON DELETE CASCADE
);

-- ==================
-- Liquidaciones (cierre mensual)
-- ==================
CREATE TABLE IF NOT EXISTS liquidaciones (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  anio      INTEGER NOT NULL,
  mes       INTEGER NOT NULL CHECK(mes BETWEEN 1 AND 12),
  estado    TEXT    NOT NULL CHECK(estado IN ('BORRADOR','CERRADO')),
  creado_en TEXT    NOT NULL,
  cerrado_en TEXT,
  nota      TEXT,
  UNIQUE (anio, mes)
);

CREATE TABLE IF NOT EXISTS liquidacion_detalle (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  liquidacion_id     INTEGER NOT NULL,
  empleado_id        INTEGER NOT NULL,
  minutos_pagados    INTEGER NOT NULL,
  pago_hora_cent     INTEGER NOT NULL,
  monto_cent         INTEGER NOT NULL,
  FOREIGN KEY (liquidacion_id) REFERENCES liquidaciones(id) ON DELETE CASCADE,
  FOREIGN KEY (empleado_id) REFERENCES empleados(id),
  UNIQUE (liquidacion_id, empleado_id)
);
