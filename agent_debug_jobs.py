import re
from typing import List, Dict, Optional, Tuple

from db_utils_blue import get_blue_db_connection

# Heuristischer Finder für kommende Jobs eines Masseurs (BLUE-DB)
# Sucht in information_schema nach Tabellen mit plausiblen Spaltennamen und versucht
# eine generische Abfrage. Liefert eine kurze Liste mit Datum, Location, Beschreibung.

CANDIDATE_USER_COLS = [
    "user_id", "masseur_id", "provider_id", "employee_id", "staff_id"
]
CANDIDATE_DATE_COLS = [
    "date", "datum", "start", "start_time", "startdate", "job_date", "event_date"
]
CANDIDATE_LOCATION_COLS = [
    "location", "ort", "city", "stadt", "place", "adresse", "address"
]
CANDIDATE_DESC_COLS = [
    "beschreibung", "description", "title", "job_title", "name"
]

MAX_TABLES_TO_TRY = 20


def _fetch_db_name(cursor) -> Optional[str]:
    cursor.execute("SELECT DATABASE() AS db")
    row = cursor.fetchone()
    return row.get("db") if row else None


def _find_candidate_tables(cursor, dbname: str) -> List[Tuple[str, Dict[str, str]]]:
    # Suche Tabellen, die mindestens einen der Nutzer- und einen der Datums-Spalten enthalten
    # Hole Metadaten einmal und gruppiere nach Tabelle
    placeholders = ",".join(["%s"] * (len(CANDIDATE_USER_COLS) + len(CANDIDATE_DATE_COLS) + len(CANDIDATE_LOCATION_COLS) + len(CANDIDATE_DESC_COLS)))
    wanted = CANDIDATE_USER_COLS + CANDIDATE_DATE_COLS + CANDIDATE_LOCATION_COLS + CANDIDATE_DESC_COLS
    sql = (
        "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND COLUMN_NAME IN (" + placeholders + ")"
    )
    cursor.execute(sql, [dbname] + wanted)
    by_table: Dict[str, Dict[str, List[str]]] = {}
    for row in cursor.fetchall():
        t = row["TABLE_NAME"]
        c = row["COLUMN_NAME"]
        d = by_table.setdefault(t, {"user": [], "date": [], "loc": [], "desc": []})
        if c in CANDIDATE_USER_COLS:
            d["user"].append(c)
        if c in CANDIDATE_DATE_COLS:
            d["date"].append(c)
        if c in CANDIDATE_LOCATION_COLS:
            d["loc"].append(c)
        if c in CANDIDATE_DESC_COLS:
            d["desc"].append(c)
    candidates: List[Tuple[str, Dict[str, str]]] = []
    for table, groups in by_table.items():
        if groups["user"] and groups["date"]:
            # Wähle je Gruppe eine bevorzugte Spalte
            chosen = {
                "user": groups["user"][0],
                "date": groups["date"][0],
                "loc": groups["loc"][0] if groups["loc"] else None,
                "desc": groups["desc"][0] if groups["desc"] else None,
            }
            candidates.append((table, chosen))
    return candidates[:MAX_TABLES_TO_TRY]


def get_upcoming_jobs_for_user(user_id: int, limit: int = 3) -> List[Dict[str, Optional[str]]]:
    conn = get_blue_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        dbname = _fetch_db_name(cursor)
        if not dbname:
            return []
        tables = _find_candidate_tables(cursor, dbname)
        results: List[Dict[str, Optional[str]]] = []
        for table, cols in tables:
            user_col = cols["user"]
            date_col = cols["date"]
            loc_col = cols.get("loc")
            desc_col = cols.get("desc")
            sel_cols = [date_col]
            if loc_col:
                sel_cols.append(loc_col)
            if desc_col:
                sel_cols.append(desc_col)
            select_expr = ", ".join(sel_cols)
            sql = (
                f"SELECT {select_expr} FROM `{table}` "
                f"WHERE `{user_col}` = %s AND `{date_col}` >= CURDATE() "
                f"ORDER BY `{date_col}` ASC LIMIT %s"
            )
            try:
                cursor.execute(sql, (user_id, limit))
                rows = cursor.fetchall() or []
                if rows:
                    for r in rows:
                        results.append({
                            "date": str(r.get(date_col)) if date_col in r else None,
                            "location": r.get(loc_col) if loc_col else None,
                            "description": r.get(desc_col) if desc_col else None,
                            "table": table,
                        })
                if results:
                    break  # erste Tabelle mit Treffern reicht
            except Exception:
                continue  # nächste Kandidatentabelle probieren
        return results[:limit]
    finally:
        cursor.close()
        conn.close()
