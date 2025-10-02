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


# Fallback: Bids ohne Zeitfilter – liefert wenigstens Beschriftungen (und ggf. Datum/Adresse)
def get_bids_tasks_any(user_id: int, limit: int = 3) -> List[Dict[str, Optional[str]]]:
    conn = get_blue_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT DATABASE() AS db")
        dbrow = cursor.fetchone() or {}
        dbname = dbrow.get("db")
        loc_col = "loc_address"
        loc_fk_col = "loc_task_id"  # bevorzugt laut Screenshot
        lang_cols = {
            "title": None,
            "desc": None,
            "instr": None,
        }
        # Bevorzugter FK laut Vorgabe: 'tasklang_task_id'
        lang_fk_col = "tasklang_task_id"
        lang_lang_col = None
        if dbname:
            try:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='tbl_task_locations'",
                    (dbname,)
                )
                cols = {r["COLUMN_NAME"].lower() for r in cursor.fetchall()}
                for candidate in ("loc_address", "name", "title", "location", "address"):
                    if candidate in cols:
                        loc_col = candidate
                        break
                for fk_cand in ("loc_task_id", "task_location_id", "location_id", "id"):
                    if fk_cand in cols:
                        loc_fk_col = fk_cand
                        break
            except Exception:
                pass
            # Prüfe Spalten in tbl_tasks_lang
            try:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='tbl_tasks_lang'",
                    (dbname,)
                )
                cols = {r["COLUMN_NAME"].lower() for r in cursor.fetchall()}
                # Titelfeld ermitteln
                for c in ("task_titel", "task_title", "title", "task_name"):
                    if c in cols:
                        lang_cols["title"] = c
                        break
                for c in ("task_description", "description"):
                    if c in cols:
                        lang_cols["desc"] = c
                        break
                for c in ("task_instruction", "instruction", "instructions"):
                    if c in cols:
                        lang_cols["instr"] = c
                        break
                for c in ("tasklang_task_id", "task_id", "tl_task_id", "task_ref_id", "task_lang_task_id", "taskid"):
                    if c in cols:
                        lang_fk_col = c
                        break
                for c in ("lang", "language", "locale"):
                    if c in cols:
                        lang_lang_col = c
                        break
            except Exception:
                pass
        # Festes Sprachschema laut Vorgabe
        lang_select_sql = ", tl.task_title AS task_title, tl.task_description AS task_description, tl.task_instruction AS task_instruction"
        lang_join = "LEFT JOIN tbl_tasks_lang tl ON tl.tasklang_task_id = t.task_id "
        lang_where = ""
        sql = (
            f"SELECT b.bid_id, b.bid_task_id, t.task_deliver_by AS date, l.{loc_col} AS location, t.task_identifier AS description"
            f"{lang_select_sql} "
            "FROM tbl_task_bids b "
            "JOIN tbl_tasks t ON t.task_id = b.bid_task_id "
            f"LEFT JOIN tbl_task_locations l ON l.{loc_fk_col} = t.task_id "
            f"{lang_join}"
            "WHERE b.bid_bidder_id = %s "
            f"{lang_where}"
            "ORDER BY (t.task_deliver_by IS NULL), t.task_deliver_by ASC LIMIT %s"
        )
        try:
            cursor.execute(sql, (user_id, limit))
        except Exception:
            # Fallback: ohne Sprach-Join erneut versuchen
            sql_no_lang = (
                f"SELECT b.bid_id, b.bid_task_id, t.task_deliver_by AS date, l.{loc_col} AS location, t.task_identifier AS description "
                "FROM tbl_task_bids b "
                "JOIN tbl_tasks t ON t.task_id = b.bid_task_id "
                f"LEFT JOIN tbl_task_locations l ON l.{loc_fk_col} = t.task_id "
                "WHERE b.bid_bidder_id = %s "
                "ORDER BY (t.task_deliver_by IS NULL), t.task_deliver_by ASC LIMIT %s"
            )
            cursor.execute(sql_no_lang, (user_id, limit))
        rows = cursor.fetchall() or []
        return [
            {
                "date": r.get("date"),
                "location": r.get("location"),
                "description": r.get("description"),
                "task_id": r.get("bid_task_id"),
                "bid_id": r.get("bid_id"),
                "task_title": r.get("task_title"),
                "task_description": r.get("task_description"),
                "task_instruction": r.get("task_instruction"),
                "table": "tbl_task_bids"
            }
            for r in rows
        ]
    finally:
        cursor.close()
        conn.close()


# Präziser Pfad über Bids: tbl_task_bids -> tbl_tasks -> tbl_task_locations
# Felder:
#   - tbl_task_bids.bid_bidder_id (User/Masseur)
#   - tbl_task_bids.bid_id, tbl_task_bids.bid_task_id
#   - tbl_tasks.task_identifier, tbl_tasks.task_deliver_by, tbl_tasks.task_location_id
#   - tbl_task_locations.loc_address
def get_upcoming_tasks_via_bids(user_id: int, limit: int = 3) -> List[Dict[str, Optional[str]]]:
    conn = get_blue_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Prüfe existierende Spalten in tbl_task_locations für Location-Feld
        cursor.execute("SELECT DATABASE() AS db")
        dbrow = cursor.fetchone() or {}
        dbname = dbrow.get("db")
        loc_col = "loc_address"
        loc_fk_col = "loc_task_id"
        lang_cols = {
            "title": None,
            "desc": None,
            "instr": None,
        }
        lang_fk_col = "task_id"
        lang_lang_col = None
        if dbname:
            try:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='tbl_task_locations'",
                    (dbname,)
                )
                cols = {r["COLUMN_NAME"].lower() for r in cursor.fetchall()}
                for candidate in ("loc_address", "name", "title", "location", "address"):
                    if candidate in cols:
                        loc_col = candidate
                        break
                for fk_cand in ("loc_task_id", "task_location_id", "location_id", "id"):
                    if fk_cand in cols:
                        loc_fk_col = fk_cand
                        break
            except Exception:
                pass
            # Prüfe Spalten in tbl_tasks_lang
            try:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='tbl_tasks_lang'",
                    (dbname,)
                )
                cols = {r["COLUMN_NAME"].lower() for r in cursor.fetchall()}
                for c in ("task_titel", "task_title", "title", "task_name"):
                    if c in cols:
                        lang_cols["title"] = c
                        break
                for c in ("task_description", "description"):
                    if c in cols:
                        lang_cols["desc"] = c
                        break
                for c in ("task_instruction", "instruction", "instructions"):
                    if c in cols:
                        lang_cols["instr"] = c
                        break
                for c in ("task_id", "tl_task_id", "task_ref_id", "task_lang_task_id", "taskid"):
                    if c in cols:
                        lang_fk_col = c
                        break
                for c in ("lang", "language", "locale"):
                    if c in cols:
                        lang_lang_col = c
                        break
            except Exception:
                pass
        # Festes Sprachschema laut Vorgabe
        lang_select_sql = ", tl.task_title AS task_title, tl.task_description AS task_description, tl.task_instruction AS task_instruction"
        lang_join = "LEFT JOIN tbl_tasks_lang tl ON tl.tasklang_task_id = t.task_id "
        lang_where = ""
        sql = (
            f"SELECT b.bid_id, b.bid_task_id, t.task_deliver_by AS date, l.{loc_col} AS location, t.task_identifier AS description"
            f"{lang_select_sql} "
            "FROM tbl_task_bids b "
            "JOIN tbl_tasks t ON t.task_id = b.bid_task_id "
            f"LEFT JOIN tbl_task_locations l ON l.{loc_fk_col} = t.task_id "
            f"{lang_join}"
            "WHERE b.bid_bidder_id = %s AND t.task_deliver_by >= NOW() "
            f"{lang_where}"
            "ORDER BY t.task_deliver_by ASC LIMIT %s"
        )
        try:
            cursor.execute(sql, (user_id, limit))
        except Exception:
            # Fallback: ohne Sprach-Join erneut versuchen
            sql_no_lang = (
                f"SELECT b.bid_id, b.bid_task_id, t.task_deliver_by AS date, l.{loc_col} AS location, t.task_identifier AS description "
                "FROM tbl_task_bids b "
                "JOIN tbl_tasks t ON t.task_id = b.bid_task_id "
                f"LEFT JOIN tbl_task_locations l ON l.{loc_fk_col} = t.task_id "
                "WHERE b.bid_bidder_id = %s AND t.task_deliver_by >= NOW() "
                "ORDER BY t.task_deliver_by ASC LIMIT %s"
            )
            cursor.execute(sql_no_lang, (user_id, limit))
        rows = cursor.fetchall() or []
        return [
            {
                "date": r.get("date"),
                "location": r.get("location"),
                "description": r.get("description"),
                "task_id": r.get("bid_task_id"),
                "bid_id": r.get("bid_id"),
                "task_title": r.get("task_title"),
                "task_description": r.get("task_description"),
                "task_instruction": r.get("task_instruction"),
                "table": "tbl_task_bids"
            }
            for r in rows
        ]
    finally:
        cursor.close()
        conn.close()


# Präzise Variante für das bekannte BLUE-Schema
# Tabellen:
#   - tbl_tasks (task_user_id, task_identifier, task_deliver_by, task_location_id)
# Gibt Liste mit {date, location, description} zurück.
def get_upcoming_tasks_precise(user_id: int, limit: int = 3) -> List[Dict[str, Optional[str]]]:
    conn = get_blue_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Versuche bevorzugt 'loc_address' als Location, ansonsten alternative Spalten
        # Wir prüfen via information_schema, welche Spalten existieren.
        cursor.execute("SELECT DATABASE() AS db")
        dbrow = cursor.fetchone() or {}
        dbname = dbrow.get("db")
        loc_col = "loc_address"
        if dbname:
            try:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='tbl_task_locations'",
                    (dbname,)
                )
                cols = {r["COLUMN_NAME"].lower() for r in cursor.fetchall()}
                for candidate in ("loc_address", "name", "title", "location", "address"):
                    if candidate in cols:
                        loc_col = candidate
                        break
            except Exception:
                pass
        sql = (
            f"SELECT t.task_deliver_by AS date, l.{loc_col} AS location, t.task_identifier AS description "
            "FROM tbl_tasks t "
            "LEFT JOIN tbl_task_locations l ON l.task_location_id = t.task_location_id "
            "WHERE t.task_user_id = %s AND t.task_deliver_by >= NOW() "
            "ORDER BY t.task_deliver_by ASC LIMIT %s"
        )
        cursor.execute(sql, (user_id, limit))
        rows = cursor.fetchall() or []
        return [
            {
                "date": str(r.get("date")) if r.get("date") is not None else None,
                "location": r.get("location"),
                "description": r.get("description"),
                "table": "tbl_tasks"
            }
            for r in rows
        ]
    finally:
        cursor.close()
        conn.close()
