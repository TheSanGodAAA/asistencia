from pathlib import Path

from openpyxl import Workbook

from db.database import get_conn, PROJECT_ROOT


def _fmt_horas(minutos: int) -> str:
    hh = int(minutos) // 60
    mm = int(minutos) % 60
    return f"{hh:02d}:{mm:02d}"


def _resolve_cols(conn) -> tuple[str, str, str]:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(liquidacion_detalle)").fetchall()}

    monto_col = "monto_cent" if "monto_cent" in cols else "monto_bruto_cent"
    if "vales_cent" in cols:
        vales_col = "vales_cent"
    elif "vales_mes_cent" in cols:
        vales_col = "vales_mes_cent"
    else:
        vales_col = None

    if "monto_final_cent" in cols:
        final_col = "monto_final_cent"
    elif "monto_neto_cent" in cols:
        final_col = "monto_neto_cent"
    else:
        final_col = "monto_cent"

    vales_expr = f"COALESCE(ld.{vales_col}, 0)" if vales_col else "0"
    return f"ld.{monto_col}", vales_expr, f"COALESCE(ld.{final_col}, ld.{monto_col})"


def build_liquidacion_export_rows(anio: int, mes: int) -> list[tuple[int, str, str, str, str, str]]:
    """Devuelve filas listas para export (TXT/XLSX).

    Formato por fila:
      (ID, Nombre, HorasTrabajadas, MontoAntesVale, Vales, MontoFinal)
    """
    with get_conn() as conn:
        liq = conn.execute(
            "SELECT id FROM liquidaciones WHERE anio=? AND mes=?",
            (anio, mes),
        ).fetchone()

        if not liq:
            raise RuntimeError(f"No existe liquidación para {anio}-{mes:02d}")

        liquidacion_id = int(liq[0])
        monto_expr, vales_expr, final_expr = _resolve_cols(conn)
        query = f"""
            SELECT ld.empleado_id,
                   e.nombre,
                   ld.minutos_pagados,
                   {monto_expr} AS monto_bruto_cent,
                   {vales_expr} AS vales_cent,
                   {final_expr} AS monto_final_cent
            FROM liquidacion_detalle ld
            JOIN empleados e ON e.id = ld.empleado_id
            WHERE ld.liquidacion_id = ?
            ORDER BY ld.empleado_id
        """
        rows = conn.execute(query, (liquidacion_id,)).fetchall()

    records: list[tuple[int, str, str, str, str, str]] = []
    for emp_id, nombre, minutos, bruto_cent, vales_cent, final_cent in rows:
        bruto_uyu = int(bruto_cent) / 100.0
        vales_uyu = int(vales_cent) / 100.0
        final_uyu = int(final_cent) / 100.0
        records.append(
            (
                int(emp_id),
                str(nombre),
                _fmt_horas(int(minutos)),
                f"{bruto_uyu:.2f}",
                f"{vales_uyu:.2f}",
                f"{final_uyu:.2f}",
            )
        )
    return records


def export_liquidacion_txt_xlsx(anio: int, mes: int, out_dir: Path | None = None) -> tuple[Path, Path]:
    records = build_liquidacion_export_rows(anio, mes)

    target = out_dir or (PROJECT_ROOT / "data" / "processed")
    target.mkdir(parents=True, exist_ok=True)

    out_txt = target / f"liquidacion_{anio}_{mes:02d}.txt"
    out_xlsx = target / f"liquidacion_{anio}_{mes:02d}.xlsx"

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("ID\tNombre\tHorasTrabajadas\tMonto(antes de vale)\tVales\tMontoFinal(luego de vales)\n")
        for rec in records:
            f.write("\t".join(map(str, rec)) + "\n")

    wb = Workbook()
    ws = wb.active
    ws.title = "Liquidacion"
    ws.append([
        "ID",
        "Nombre",
        "HorasTrabajadas",
        "Monto(antes de vale)",
        "Vales",
        "MontoFinal(luego de vales)",
    ])
    for rec in records:
        ws.append(list(rec))
    wb.save(out_xlsx)

    return out_txt, out_xlsx
