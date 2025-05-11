from db_utils_blue import get_blue_db_connection

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
