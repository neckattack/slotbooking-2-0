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
    # Globale Terminübersicht für neckattack (z.B. "Welche Termine haben wir morgen?" oder "Welche Termine hat neckattack am <Datum>?")
    import re
    if channel == "email":
        # Suche nach einem Datum in der Frage (z.B. "morgen", "am 25.04.2025", "am 25.4.")
        msg_lc = user_message.lower()
        # 1. "morgen"
        if "morgen" in msg_lc:
            from datetime import timedelta
            datum = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            datum_nice = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
        else:
            # 2. explizites Datum suchen
            match = re.search(r'am (\d{1,2})[\./](\d{1,2})(?:[\./](\d{2,4}))?', msg_lc)
            if match:
                tag, monat, jahr = match.groups()
                if not jahr:
                    jahr = str(datetime.now().year)
                if len(jahr) == 2:
                    jahr = '20' + jahr
                datum = f"{jahr}-{int(monat):02d}-{int(tag):02d}"
                datum_nice = f"{int(tag):02d}.{int(monat):02d}.{jahr}"
            else:
                datum = datetime.now().strftime('%Y-%m-%d')
                datum_nice = datetime.now().strftime('%d.%m.%Y')
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            sql = """
                SELECT c.name AS firma, t.time_start, t.time_end, r.name AS kunde, r.email AS kunde_email
                FROM dates d
                JOIN clients c ON d.client_id = c.id
                JOIN times t ON t.date_id = d.id
                LEFT JOIN reservations r ON r.time_id = t.id
                WHERE d.date = %s
                ORDER BY c.name, t.time_start
            """
            cursor.execute(sql, (datum,))
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            if not rows:
                antwort = f"Hallo,\n\nfür den {datum_nice} sind keine Termine oder Anmeldungen im System eingetragen.\n\nViele Grüße\nIhr neckattack-Team"
            else:
                antwort = f"Hallo,\n\nhier sind alle Termine und Anmeldungen für den {datum_nice}:\n"
                aktuelle_firma = None
                for row in rows:
                    if row['firma'] != aktuelle_firma:
                        antwort += f"\nFirma: {row['firma']}\n"
                        aktuelle_firma = row['firma']
                    kunde = row['kunde'] if row['kunde'] else "FREI"
                    antwort += f"  {row['time_start']}-{row['time_end']}: {kunde}"
                    if row['kunde_email']:
                        antwort += f" ({row['kunde_email']})"
                    antwort += "\n"
                antwort += "\nViele Grüße\nIhr neckattack-Team"
            return antwort
        except Exception as e:
            return f"Hallo,\n\nes gab einen Fehler bei der Terminabfrage: {e}\n\nViele Grüße\nIhr neckattack-Team"
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
        return "Entschuldigung, ich kann aus Sicherheitsgründen nur Informationen aus der Datenbank abrufen, aber keine Änderungen vornehmen. Bitte stelle deine Frage so, dass ich dir mit einer Auskunft helfen kann – zum Beispiel zu bestehenden Terminen oder Kunden. Falls du Unterstützung brauchst, melde dich gern direkt beim Support!"
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
