import os
import openai
from datetime import datetime
from agent_core import find_next_appointment_for_name
from db_utils import get_db_connection

openai.api_key = os.environ.get("OPENAI_API_KEY")

def load_knowledge():
    try:
        with open("docs/knowledge.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def agent_respond(user_message, channel="chat", user_email=None):
    """
    Liefert eine GPT-Antwort mit neckattack-Kontext und DB-Infos.
    - user_message: Die Frage/Bitte des Nutzers (Mailtext, Chat, ...)
    - channel: "chat", "email" etc.
    - user_email: falls bekannt, für Kontext (z.B. bei E-Mail)
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    db_context = ""
    knowledge = load_knowledge()
    system_prompt = (
        f"Du bist ein KI-Assistent für die Slotbuchung bei neckattack. Das heutige Datum ist {today_str}.\n"
        "Du kennst das folgende Datenbankschema und kannst SQL-Statements generieren, um beliebige Nutzerfragen zu beantworten.\n"
        "Führe niemals destructive Queries wie DROP, DELETE, UPDATE ohne explizite Freigabe aus!\n"
        "Antworte immer auf Deutsch.\n"
        f"Datenbankschema (Knowledge):\n{knowledge}\n"
        f"(Kanal: {channel})\n"
        f"Datenbank-Kontext: {db_context}\n"
    )
    # Chain-of-Thought für komplexe Masseur-Fragen (z.B. "Welche Termine habe ich morgen?")
    if user_email and any(kw in user_message.lower() for kw in ["meine termine", "welche termine habe ich", "slots morgen", "freie termine morgen", "meine buchungen morgen", "welche kunden habe ich morgen"]):
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            # Schritt 1: Masseur-ID zur E-Mail
            cursor.execute("SELECT id FROM admin WHERE email = %s", (user_email,))
            masseur = cursor.fetchone()
            if not masseur:
                return "Keine Masseur-ID zur angegebenen E-Mail gefunden."
            masseur_id = masseur["id"]
            # Schritt 2: Firmen/Date-IDs für morgen
            from datetime import timedelta
            morgen = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            cursor.execute("SELECT id, client_id FROM dates WHERE masseur_id = %s AND date = %s", (masseur_id, morgen))
            date_rows = cursor.fetchall()
            if not date_rows:
                return "Für morgen sind Sie keinem Unternehmen zugeordnet."
            results = []
            for date in date_rows:
                date_id = date["id"]
                # Schritt 3: Alle Slots und Reservierungen für diese Date-ID
                cursor.execute("""
                    SELECT t.time_start, t.time_end, r.name AS kunde, r.email AS kunde_email
                    FROM times t
                    LEFT JOIN reservations r ON t.id = r.time_id
                    WHERE t.date_id = %s
                    ORDER BY t.time_start
                """, (date_id,))
                slots = cursor.fetchall()
                for slot in slots:
                    kunde = slot["kunde"] if slot["kunde"] else "FREI"
                    results.append(f"{slot['time_start']}-{slot['time_end']}: {kunde}")
            cursor.close()
            conn.close()
            if not results:
                return "Für morgen sind keine Slots oder Reservierungen vorhanden."
            return "Ihre Termine und freie Slots für morgen:\n" + "\n".join(results)
        except Exception as e:
            return f"[Fehler bei der Chain-of-Thought-Abfrage: {e}]"
    # Standard: Text-zu-SQL-Flow
    # 1. Frage GPT nach passendem SQL-Query für die Nutzerfrage
    sql_prompt = (
        system_prompt +
        "\nFormuliere für die folgende Nutzerfrage ein passendes SQL-SELECT-Statement (ohne Erklärtext, nur das SQL!):\n" +
        user_message
    )
    sql_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": sql_prompt}]
    )
    sql_query = sql_response.choices[0].message['content'].strip()
    # Sicherheits-Check: Nur SELECTs erlauben
    if not sql_query.lower().startswith("select"):
        return "[Fehler: Nur SELECT-Abfragen sind erlaubt!]"
    # 2. Führe das SQL-Statement aus
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if not rows:
            return "Keine passenden Daten gefunden."
        # 3. Formatiere das Ergebnis für den Nutzer
        result_lines = []
        for row in rows:
            result_lines.append(", ".join(f"{k}: {v}" for k, v in row.items()))
        result_text = "\n".join(result_lines)
        return f"Antwort aus der Datenbank:\n{result_text}"
    except Exception as e:
        return f"[Fehler bei der Datenbankabfrage: {e}]"
