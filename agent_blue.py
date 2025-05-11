from db_utils_blue import get_blue_db_connection


def get_user_info_by_email(email):
    """
    Liefert ein Dict mit Vorname, Nachname, Rolle und user_id für eine gegebene E-Mail.
    Rolle: 'masseur' wenn user_is_provider=1, sonst 'kunde'.
    Gibt None zurück, wenn nicht gefunden.
    """
    conn = get_blue_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, user_first_name, user_last_name, user_is_provider FROM tbl_users WHERE user_email = %s", (email,))
        row = cursor.fetchone()
        if not row:
            return None
        role = 'masseur' if row['user_is_provider'] == 1 else 'kunde'
        return {
            'user_id': row['user_id'],
            'first_name': row['user_first_name'],
            'last_name': row['user_last_name'],
            'role': role
        }
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
