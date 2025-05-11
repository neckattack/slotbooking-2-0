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
    # Schlüsselwörter für DB-Fragen
    db_keywords = [
        "termin", "termine", "slot", "slots", "kunde", "kunden", "reservierung", "reservierungen",
        "sql", "datenbank", "gebucht", "frei", "gebuchte zeiten", "freie zeiten", "einsatz", "einsätze"
    ]
    system_prompt = (
        f"Du bist ein KI-Assistent für die Slotbuchung bei neckattack. Das heutige Datum ist {today_str}.\n"
        "Du kennst das folgende Datenbankschema und kannst SQL-Statements generieren, um Nutzerfragen zu beantworten, wenn diese explizit nach Datenbankinhalten oder nach Terminen, Slots, Kunden, Reservierungen, gebuchten/freien Zeiten oder Einsätzen fragen.\n"
        "WICHTIG: Versuche IMMER zuerst, die Nutzerfrage anhand der Knowledgebase als FAQ zu beantworten. Nur wenn wirklich explizit nach Datenbankinhalten, Listen, Statistiken oder konkreten Werten gefragt wird, generiere ein SQL-Statement.\n"
        "Wenn du ein SQL-Statement generierst, gib NUR das SQL-Statement zurück (ohne Erklärtext, ohne Codeblock, ohne Präfix). In allen anderen Fällen gib direkt die Antwort für die E-Mail zurück.\n"
        "Achte bei deinen Antworten IMMER auf eine natürliche, freundliche und sehr übersichtliche Formatierung: Nutze für Schritt-für-Schritt-Anleitungen IMMER nummerierte Listen (jede Anweisung als eigener Listenpunkt) und trenne Absätze immer durch eine Leerzeile. Schreibe keine Fließtexte, sondern gliedere die Antwort wie eine echte, gut lesbare E-Mail. Keine technischen Labels, keine HTML-Tags, keine FAQ-Kennzeichnung.\n"
        "Führe niemals destructive Queries wie DROP, DELETE, UPDATE ohne explizite Freigabe aus!\n"
        "Antworte immer auf Deutsch.\n"
        f"Datenbankschema (Knowledge):\n{knowledge}\n"
        f"(Kanal: {channel})\n"
        f"Datenbank-Kontext: {db_context}\n"
    )
    import re
    import unicodedata
    def normalize(text):
        text = text.lower().strip()
        text = unicodedata.normalize('NFKD', text)
        text = re.sub(r'[\W_]+', '', text)
        return text

    # Prüfe, ob die Nutzerfrage wirklich eine DB-Abfrage ist
    user_message_norm = normalize(user_message)
    # FAQ-First: Prüfe, ob die Frage mit typischen FAQ-Formulierungen beginnt
    faq_starts = [
        "wie kann ich", "wie funktioniert", "was muss ich tun", "wie nehme ich", "wie akzeptiere ich", "wie bekomme ich", "wie melde ich mich", "wo finde ich"
    ]
    user_message_lower = user_message.lower().strip()
    is_faq = any(user_message_lower.startswith(start) for start in faq_starts)

    # Neue Logik: Nur wenn explizit nach Datenbankinhalten gefragt wird ("wie viele", "zeige mir", "liste", "welche kunden", "sql")
    # AI-first: GPT entscheidet, ob FAQ oder SQL nötig ist
    import logging
    import re
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=512,
            temperature=0.2
        )
        antwort = response.choices[0].message.content.strip()
        # Prüfe, ob die Antwort wie ein SQL-Statement aussieht
        sql_pattern = re.compile(r'^(SELECT|SHOW|DESCRIBE|WITH) ', re.IGNORECASE)
        if sql_pattern.match(antwort):
            # SQL ausführen
            try:
                conn = get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(antwort)
                rows = cursor.fetchall()
                cursor.close()
                conn.close()
                if not rows:
                    return "Es wurden keine passenden Daten gefunden."
                # Ergebnis formatieren
                result_lines = []
                for row in rows:
                    result_lines.append(", ".join(f"{k}: {v}" for k, v in row.items()))
                result_text = "\n".join(result_lines)
                return result_text
            except Exception as e:
                logging.error(f"[DB-Exception] Fehler bei der Datenbankabfrage für Frage '{user_message}': {e}")
                return "Entschuldigung, es gab einen Fehler bei der Datenbankabfrage. Bitte versuche es später erneut oder kontaktiere den Support."
        # Wenn kein SQL, direkt als FAQ-Antwort zurückgeben
        if not antwort:
            logging.error(f"[FAQ-Fehler] Leere Antwort von OpenAI für Frage: {user_message}")
            return "Entschuldigung, ich konnte deine Frage gerade nicht beantworten. Bitte versuche es später erneut oder kontaktiere den Support."
        return antwort
    except Exception as e:
        logging.error(f"[FAQ/DB-Exception] Fehler bei der Antwort für Frage '{user_message}': {e}")
        return "Entschuldigung, ich konnte deine Frage gerade nicht beantworten. Bitte versuche es später erneut oder kontaktiere den Support."
