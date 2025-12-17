import re
from datetime import datetime

# Ejemplo línea:
#      3   1/11/2025 7:59       M/Ent
#      3  4/11/2025 11:55 Sal Hrs Ext

LINE_RE = re.compile(
    r"^\s*(?P<ac_no>\d+)\s+"
    r"(?P<fecha>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?P<hora>\d{1,2}:\d{2})\s+"
    r"(?P<estado>.+?)\s*$"
)

def _map_estado(estado_raw: str) -> str | None:
    s = " ".join(estado_raw.strip().split())  # normaliza espacios
    s_low = s.lower()

    if s_low == "m/ent":
        return "ENT"
    if s_low == "m/sal":
        return "SAL"
    if s_low == "ent hrs ext":
        return "ENT"
    if s_low == "sal hrs ext":
        return "SAL"

    # Si aparece algún estado raro, lo ignoramos por ahora
    return None

def parse_line(line: str) -> dict | None:
    line = line.rstrip("\n")
    if not line.strip():
        return None

    # saltear headers típicos
    low = line.lower()
    if "ac-no" in low or "estado" in low or "nvoestado" in low:
        return None

    m = LINE_RE.match(line)
    if not m:
        return None

    ac_no = int(m.group("ac_no"))
    fecha = m.group("fecha")
    hora = m.group("hora")
    estado_raw = m.group("estado")

    tipo = _map_estado(estado_raw)
    if tipo is None:
        return None

    ts = datetime.strptime(f"{fecha} {hora}", "%d/%m/%Y %H:%M")

    return {
        "ac_no": ac_no,
        "ts": ts.isoformat(timespec="seconds"),
        "tipo": tipo,              # ENT / SAL
        "estado_raw": estado_raw,  # por si querés auditar
    }

def parse_file(path: str):
    with open(path, encoding="latin-1") as f:
        for line in f:
            rec = parse_line(line)
            if rec:
                yield rec
