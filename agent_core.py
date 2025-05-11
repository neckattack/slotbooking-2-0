import os
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
from difflib import get_close_matches

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT", 3306))
    )

# --- Kern-Logik: Termin-Suche, Fuzzy-Suche, Kontextaufbau ---
def find_next_appointment_for_name(name):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    today_str = datetime.now().strftime('%Y-%m-%d')
    db_context = ""
    # Firmensuche (wie Chatbot)
    cursor.execute("SELECT id, name FROM clients WHERE name LIKE %s", (f"%{name}%",))
    firmen_treffer = cursor.fetchall()
    if firmen_treffer:
        db_context += f" Firmenname gefunden: {', '.join([f['name'] for f in firmen_treffer])}."
    else:
        cursor.execute("SELECT name FROM clients")
        alle_firmen = [r['name'] for r in cursor.fetchall()]
        vorschlaege_firma = get_close_matches(name, alle_firmen, n=3, cutoff=0.4)
        if not alle_firmen:
            db_context += " Es sind keine Firmen in der Datenbank hinterlegt."
        elif vorschlaege_firma:
            db_context += f" Kein exakter Firmenname gefunden. Ähnliche Firmennamen: {', '.join(vorschlaege_firma)}."
        else:
            db_context += f" Kein Firmenname oder ähnliche Firmen gefunden."
    # Termin-Suche
    cursor.execute("""
        SELECT MIN(datum) as naechster_termin, kunde FROM termine
        WHERE kunde LIKE %s AND datum >= %s
    """, (f"%{name}%", today_str))
    row = cursor.fetchone()
    if row and row['naechster_termin']:
        db_context += f" Nächster Termin für {name}: {row['naechster_termin']} ."
    else:
        cursor.execute("SELECT DISTINCT kunde FROM termine WHERE kunde IS NOT NULL")
        alle_kunden = [r['kunde'] for r in cursor.fetchall()]
        vorschlaege_kunde = get_close_matches(name, alle_kunden, n=3, cutoff=0.4)
        if not alle_kunden:
            db_context += " Es sind keine Kunden in der Datenbank hinterlegt."
        elif vorschlaege_kunde:
            db_context += f" Kein exakter Kundenname gefunden. Ähnliche Kunden: {', '.join(vorschlaege_kunde)}."
        else:
            db_context += f" Kein Kunde oder ähnliche Kunden gefunden."
    cursor.close()
    conn.close()
    return db_context
