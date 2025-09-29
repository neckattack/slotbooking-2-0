from db_utils_blue import get_blue_db_connection


def get_user_info_by_email(email):
    """
    Liefert ein Dict mit Vorname, Nachname, Rolle und user_id für eine gegebene E-Mail.
    - Rolle: 'masseur' wenn user_is_provider=1, sonst 'kunde', oder 'admin' wenn in tbl_admin gefunden.
    - Gibt None zurück, wenn nicht gefunden.
    """
    conn = get_blue_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Erst in tbl_users suchen
        cursor.execute("SELECT user_id, user_first_name, user_last_name, user_is_provider FROM tbl_users WHERE user_email = %s", (email,))
        row = cursor.fetchone()
        if row:
            role = 'masseur' if row['user_is_provider'] == 1 else 'kunde'
            # Optional: dynamisch verfügbare Adressfelder ermitteln
            address = None
            try:
                # Datenbankschema ermitteln (aktuelle DB)
                cursor.execute("SELECT DATABASE() AS db")
                dbname_row = cursor.fetchone()
                dbname = dbname_row['db'] if dbname_row and 'db' in dbname_row else None
                if dbname:
                    candidate_cols = [
                        'user_street', 'user_address', 'street', 'address',
                        'user_zip', 'zip', 'postal_code',
                        'user_city', 'city',
                        'user_country', 'country'
                    ]
                    in_clause = ",".join(["'%s'" % c for c in candidate_cols])
                    meta_sql = (
                        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'tbl_users' "
                        f"AND COLUMN_NAME IN ({in_clause})"
                    )
                    cursor.execute(meta_sql, (dbname,))
                    present_cols = [r['COLUMN_NAME'] for r in cursor.fetchall()]
                    if present_cols:
                        sel_cols = ", ".join(present_cols)
                        cursor.execute(f"SELECT {sel_cols} FROM tbl_users WHERE user_email = %s", (email,))
                        addr_row = cursor.fetchone() or {}
                        parts = []
                        # Reihenfolge für schönere Darstellung
                        for key in ['user_street', 'street', 'user_address', 'address', 'user_zip', 'zip', 'postal_code', 'user_city', 'city', 'user_country', 'country']:
                            if key in addr_row and addr_row[key]:
                                parts.append(str(addr_row[key]))
                        if parts:
                            address = ", ".join(parts)
            except Exception:
                # Adress-Ermittlung ist optional; Fehler hier ignorieren
                address = None
            return {
                'user_id': row['user_id'],
                'first_name': row['user_first_name'],
                'last_name': row['user_last_name'],
                'role': role,
                'address': address
            }
        # Wenn nicht gefunden, in tbl_admin suchen
        cursor.execute("SELECT admin_username FROM tbl_admin WHERE admin_email = %s", (email,))
        admin_row = cursor.fetchone()
        if admin_row:
            return {
                'user_id': None,
                'first_name': admin_row['admin_username'],
                'last_name': '',
                'role': 'admin',
                'address': None
            }
        return None
    finally:
        cursor.close()
        conn.close()

def get_role_by_email(email):
    """
    Sucht die Rolle eines Nutzers anhand seiner E-Mail-Adresse in der BLUE-Datenbank.
    Gibt zurück: 'admin', 'kunde', 'masseur' oder None
    """
    conn = get_blue_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Annahme: Tabellen und Felder müssen ggf. angepasst werden!
    # Beispieltabellen: admins, kunden, masseure
    try:
        # Admin-Prüfung
        cursor.execute("SELECT id FROM admins WHERE email = %s", (email,))
        if cursor.fetchone():
            return 'admin'
        # Kunde-Prüfung
        cursor.execute("SELECT id FROM kunden WHERE email = %s", (email,))
        if cursor.fetchone():
            return 'kunde'
        # Masseur-Prüfung
        cursor.execute("SELECT id FROM masseure WHERE email = %s", (email,))
        if cursor.fetchone():
            return 'masseur'
        return None
    finally:
        cursor.close()
        conn.close()
