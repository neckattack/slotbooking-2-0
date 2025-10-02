from db_utils_blue import get_blue_db_connection

def debug_email_lookup(email):
    print(f"Teste Suche für E-Mail: {email}")
    conn = get_blue_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Suche in tbl_users
        cursor.execute("SELECT user_id, user_first_name, user_last_name, user_is_provider FROM tbl_users WHERE user_email = %s", (email,))
        row = cursor.fetchone()
        if row:
            role = 'masseur' if row['user_is_provider'] == 1 else 'kunde'
            print(f"[tbl_users] Gefunden: {row['user_first_name']} {row['user_last_name']} ({role})")
        else:
            print("[tbl_users] Kein Treffer.")

        # Suche in tbl_admin
        cursor.execute("SELECT admin_username FROM tbl_admin WHERE admin_email = %s", (email,))
        admin_row = cursor.fetchone()
        if admin_row:
            print(f"[tbl_admin] Gefunden: {admin_row['admin_username']} (admin)")
        else:
            print("[tbl_admin] Kein Treffer.")

    except Exception as e:
        print(f"[Fehler bei DB-Abfrage]: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Hier deine Admin-Mail einsetzen:
    debug_email_lookup("DEINE_ADMIN_EMAIL@domain.de")
