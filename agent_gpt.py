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
        import re
        # Knowledgebase aus docs/knowledge.md laden
        try:
            with open("docs/knowledge.md", "r") as f:
                knowledge = f.read()
        except Exception:
            knowledge = "(Knowledgebase konnte nicht geladen werden.)"
        # Text2SQL-Flow für ALLE Fragen
        today_str = datetime.now().strftime('%Y-%m-%d')
        system_prompt = (
            f"Du bist ein KI-Assistent für die Slotbuchung bei neckattack. Das heutige Datum ist {today_str}.\n"
            "Du kennst das folgende Datenbankschema und kannst SQL-Statements generieren, um beliebige Nutzerfragen zu beantworten.\n"
            "Führe niemals destructive Queries wie DROP, DELETE, UPDATE ohne explizite Freigabe aus!\n"
            "Antworte immer auf Deutsch.\n"
            f"Datenbankschema (Knowledge):\n{knowledge}\n"
            f"(Kanal: {channel})\n"
            "WICHTIG: Das Datum eines Termins steht IMMER in der Spalte 'date' der Tabelle 'dates' (Typ DATE). Zeitangaben stehen in 'time_start' und 'time_end' der Tabelle 'times' (Typ TIME). Um Termine in einem Zeitraum abzufragen, muss über 'dates.date' gefiltert werden.\n"
            "Bei Suchen nach Firmen/Kunden/Masseuren immer LIKE mit Wildcards verwenden, z.B. c.name LIKE '%Loges%' statt =.\n"
            "BEISPIEL: SELECT * FROM dates WHERE date >= '2025-04-25' AND date <= '2025-05-01';\n"
        )
        sql_prompt = (
            system_prompt +
            "\nGib IMMER ein SQL-SELECT-Statement zurück, das die Nutzerfrage beantwortet. KEINE Kommentare, KEINE Erklärungen, NUR das SQL-Statement!\n" +
            user_message
        )
        sql_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": sql_prompt}]
        )
        sql_query = sql_response.choices[0].message['content'].strip()
        # Fallback: Wenn kein SELECT, versuche es ein zweites Mal mit noch strengerem Prompt
        if not sql_query.lower().startswith("select"):
            fallback_prompt = (
                system_prompt +
                "\nACHTUNG: Gib JEDES MAL ein SQL-SELECT-Statement zurück, das die Nutzerfrage beantwortet. KEINE Kommentare, KEINE Erklärungen, NUR das SQL-Statement. Antworte NIEMALS mit etwas anderem als einem ausführbaren SELECT!\n" +
                user_message
            )
            sql_response_fb = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": fallback_prompt}]
            )
            sql_query = sql_response_fb.choices[0].message['content'].strip()
        # SQL-Logging: Immer ins Logfile schreiben, damit es im E-Mail-Agent-Log sichtbar ist
        import logging
        logging.info(f"[GPT-SQL-Statement] Das von GPT generierte SQL-Statement lautet:\n{sql_query}")
        if not sql_query.lower().startswith("select"):
            return "Hallo,\n\nEntschuldigung, ich kann aus Sicherheitsgründen nur Informationen aus der Datenbank abrufen, aber keine Änderungen vornehmen. Bitte stelle deine Frage so, dass ich dir mit einer Auskunft helfen kann – zum Beispiel zu bestehenden Terminen, Kunden oder Masseuren.\n\nViele Grüße\nIhr neckattack-Team"
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            if not rows:
                return "Hallo,\n\nKeine passenden Daten gefunden.\n\nViele Grüße\nIhr neckattack-Team"
            # Ergebnis formatieren
            antwort = "Hallo,\n\nHier das Ergebnis deiner Anfrage:\n"
            for row in rows:
                antwort += "- " + ", ".join(f"{k}: {v}" for k, v in row.items()) + "\n"
            antwort += "\nViele Grüße\nIhr neckattack-Team"
            return antwort
        except Exception as e:
            return f"Hallo,\n\nes gab einen Fehler bei der Datenbankabfrage: {e}\n\nViele Grüße\nIhr neckattack-Team"

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
