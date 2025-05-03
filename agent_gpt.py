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
        import difflib
        # Knowledgebase aus docs/knowledge.md laden
        try:
            with open("docs/knowledge.md", "r", encoding="utf-8") as f:
                knowledge = f.read()
        except Exception:
            knowledge = "(Knowledgebase konnte nicht geladen werden.)"
        # 1. FAQ-Logik: Suche nach passender FAQ-Antwort
        import re
        # Verbesserte FAQ-Erkennung: toleranter, case-insensitive, ignoriert Satzzeichen
        import unicodedata
        def normalize(text):
            text = text.lower().strip()
            text = unicodedata.normalize('NFKD', text)
            text = re.sub(r'[\W_]+', '', text)  # entferne Nicht-Buchstaben/Zahlen
            return text
        # FAQ-Pattern: Frage fett, Antwort eingerückt (egal ob mit 'Antwort:' oder nicht)
        faq_pattern = re.compile(r"- \*\*(.+?)\*\*\s*\n((?:\s+- .+\n?)+)")
        faqs = faq_pattern.findall(knowledge)
        user_msg_norm = normalize(user_message)
        best_match = None
        best_score = 0
        for q, a_block in faqs:
            q_norm = normalize(q)
            score = difflib.SequenceMatcher(None, user_msg_norm, q_norm).ratio()
            if score > best_score:
                best_score = score
                best_match = (q, a_block)
        # Schwelle etwas niedriger (z.B. 0.6)
        if best_match and best_score > 0.6:
            # Antwort extrahieren (erste eingerückte Zeile mit oder ohne 'Antwort:')
            antwort_zeilen = [l.strip('- ').strip() for l in best_match[1].split('\n') if l.strip()]
            antwort = ''
            for l in antwort_zeilen:
                if l.lower().startswith('antwort:'):
                    antwort = l[8:].strip()
                    break
            if not antwort and antwort_zeilen:
                antwort = antwort_zeilen[0]
            # ggf. Markdown-Links ersetzen
            antwort = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1 (\2)', antwort)
            # FAQ-Antwort wird exklusiv zurückgegeben, KEIN SQL-Flow mehr!
            return f"Hallo,\n\n{antwort}\n\nViele Grüße\nIhr neckattack-Team"
        # 2. Rückfrage bei unklaren Fragen
        # Liste bekannter Themenwörter (kannst du beliebig erweitern)
        themen = ["termin", "slot", "masseur", "kunde", "rechnung", "zahlung", "gutschrift", "einsatz", "buchung"]
        user_msg_lc = user_message.lower()
        if not any(t in user_msg_lc for t in themen) or len(user_message.strip()) < 10:
            return ("Hallo,\n\n"
                    "ich bin mir nicht sicher, was genau du wissen möchtest. "
                    "Kannst du deine Frage bitte etwas genauer formulieren? "
                    "Zum Beispiel: 'Wann wurde meine letzte Rechnung bezahlt?' oder 'Wie finde ich meine Gutschriften?'\n\n"
                    "Viele Grüße\nIhr neckattack-Team")
        # 3. Text2SQL-Flow für alle anderen Fragen
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
            # Userfreundliche, verständliche Antwort
            if len(rows) > 0 and set(rows[0].keys()) == {"date", "num_slots", "num_reservations"}:
                antwort = ("Hallo,\n\nHier die Übersicht der nächsten Termine für die gewünschte Firma. Es werden das Datum, die Anzahl der Terminslots und die Anzahl der Buchungen (Anmeldungen) angezeigt:\n\n"
                          "Datum         | Slots | Buchungen\n"
                          "------------- | ----- | ----------\n")
                for row in rows:
                    antwort += f"{row['date']} | {row['num_slots']} | {row['num_reservations']}\n"
                antwort += "\nWenn du Details zu einzelnen Buchungen wünschst, frage gerne noch einmal gezielt nach!\n\nViele Grüße\nIhr neckattack-Team"
            else:
                # Generische, aber freundlichere Ausgabe
                antwort = "Hallo,\n\nHier die Ergebnisse deiner Anfrage:\n\n"
                for i, row in enumerate(rows, 1):
                    antwort += f"{i}. " + ", ".join(f"{k}: {v}" for k, v in row.items()) + "\n"
                antwort += "\nFalls du eine noch detailliertere Übersicht brauchst, stelle deine Frage bitte noch einmal etwas genauer.\n\nViele Grüße\nIhr neckattack-Team"
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
