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
        "Nutze die Datenbank nur, wenn die Nutzerfrage eindeutig nach solchen Informationen verlangt (z.B. enthält die Frage eines der Schlüsselwörter: Termin, Slot, Kunde, Reservierung, SQL, Datenbank, gebucht, frei, gebuchte Zeiten, freie Zeiten, Einsatz).\n"
        "Alle anderen Fragen beantworte bitte als FAQ anhand des Wissens aus der Knowledgebase. Nutze die Knowledgebase flexibel als Wissensquelle und entscheide situationsgerecht, wie ausführlich du antwortest: Du kannst einzelne FAQ-Einträge zitieren, mehrere zusammenfassen oder – falls sinnvoll – eine Übersicht geben. Entscheide selbst, was für die Nutzerfrage am hilfreichsten ist.\n"
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
    # Neue Logik: Nur wenn explizit nach Datenbankinhalten gefragt wird ("wie viele", "zeige mir", "liste", "welche kunden", "sql")
    db_phrases = [
        "wie viele", "zeige mir", "liste", "welche kunden", "welche termine", "sql", "datenbank", "select "
    ]
    is_db_query = any(phrase in user_message.lower() for phrase in db_phrases)

    if is_db_query:
        # Datenbank-Modus: Generiere SQL und führe aus
        # (Hier bleibt die bestehende Logik erhalten)
        # --- GPT generiert SQL, das dann ausgeführt wird ---
        # Markiere die Antwort mit [DB]
        sql_prompt = (
            system_prompt +
            "\nFormuliere für die folgende Nutzerfrage ein passendes SQL-SELECT-Statement (ohne Erklärtext, nur das SQL!):\n" +
            user_message
        )
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                    {"role": "user", "content": sql_prompt}
                ],
                max_tokens=256,
                temperature=0.0
            )
            sql_query = response.choices[0].message.content.strip()
            # Entferne ggf. Codeblock-Markierungen wie ```sql und ```
            import re
            sql_query = re.sub(r"^```sql", "", sql_query, flags=re.IGNORECASE).strip()
            sql_query = re.sub(r"^```|```$", "", sql_query).strip()
            # Führe das SQL aus
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            if not rows:
                return "[DB] Keine passenden Daten gefunden."
            # Formatiere das Ergebnis für den Nutzer
            result_lines = []
            for row in rows:
                result_lines.append(", ".join(f"{k}: {v}" for k, v in row.items()))
            result_text = "\n".join(result_lines)
            return f"[DB] {result_text}"
        except Exception as e:
            return f"[DB] Fehler bei der Datenbankabfrage: {e}"
    else:
        # FAQ-Modus: Beantworte anhand Knowledgebase
        import logging
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
            if not antwort:
                logging.error(f"[FAQ-Fehler] Leere Antwort von OpenAI für Frage: {user_message}")
                return "Entschuldigung, ich konnte deine Frage gerade nicht beantworten. Bitte versuche es später erneut oder kontaktiere den Support."
            return antwort
        except Exception as e:
            logging.error(f"[FAQ-Exception] Fehler bei der FAQ-Antwort für Frage '{user_message}': {e}")
            return "Entschuldigung, ich konnte deine Frage gerade nicht beantworten. Bitte versuche es später erneut oder kontaktiere den Support."
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
