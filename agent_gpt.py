import os
from openai import OpenAI
from datetime import datetime
from agent_core import find_next_appointment_for_name
from db_utils import get_db_connection

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
FAQ_ONLY = os.environ.get("AGENT_FAQ_ONLY", "false").lower() == "true"  # Flag bleibt vorhanden, wird aber nicht mehr zur Blockade von SQL genutzt.

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

    # WICHTIG: E-Mails IMMER klar gegliedert mit Absätzen, Listen und Themenblöcken formatieren – keine Fließtexte! (Regel: email_formatting)
    """
    import logging
    from faq_langchain import faq_answer, faq_is_relevant
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    db_context = ""
    knowledge = load_knowledge()
    # Schlüsselwörter für DB-Fragen
    db_keywords = [
        "termin", "termine", "slot", "slots", "kunde", "kunden", "reservierung", "reservierungen",
        "sql", "datenbank", "gebucht", "frei", "gebuchte zeiten", "freie zeiten", "einsatz", "einsätze"
    ]
    # Einfache Off-Topic-Erkennung (z.B. Wetter, Smalltalk, allgemeine Fragen)
    def is_offtopic(text: str) -> bool:
        t = (text or "").lower()
        offtopic_keywords = [
            "wetter", "weather", "temperatur", "regen", "sonnig", "barcelona", "madrid", "berlin",
            "witz", "joke", "nachrichten", "news", "aktien", "börse", "football", "fußball",
            "wie gehts", "wie geht es", "smalltalk", "allgemein", "zeit", "uhrzeit"
        ]
        return any(k in t for k in offtopic_keywords)

    # Intent-Klassifizierung ohne LLM
    def classify_intent(text: str) -> str:
        try:
            if is_offtopic(text):
                return "offtopic"
            # FAISS-Check: Ist FAQ relevant?
            is_rel, _doc, _score = faq_is_relevant(text)
            if is_rel:
                return "faq"
            # Datenbank-Keywords
            t = (text or "").lower()
            if any(k in t for k in db_keywords):
                return "db"
            return "general"
        except Exception:
            return "general"

    system_prompt = (
        f"Du bist ein KI-Assistent für die Slotbuchung bei neckattack. Das heutige Datum ist {today_str}.\n"
        "Antworte so: Prüfe zuerst, ob die Knowledgebase (FAQ) relevant ist und nutze sie bevorzugt.\n"
        "Wenn die Frage klar nach Datenbankinhalten verlangt (Termine, Slots, Kunden, Reservierungen, gebucht/frei, Einsätze), darfst du SQL generieren.\n"
        "Wenn weder FAQ noch Datenbank passend sind, antworte mit deinem allgemeinen Wissen.\n"
        "WICHTIG: Wenn ein Ansatz kein gutes Ergebnis liefert, probiere den nächsten (Fallback).\n"
        "Achte bei deinen Antworten IMMER auf eine natürliche, freundliche und sehr übersichtliche Formatierung:"
        "\n- Trenne jeden Sinnabschnitt durch eine Leerzeile (Absatz)."
        "\n- Nutze für Schritt-für-Schritt-Anleitungen IMMER nummerierte Listen (jede Anweisung als eigener Listenpunkt)."
        "\n- Schreibe KEINE Fließtexte, sondern gliedere die Antwort wie eine echte, gut lesbare E-Mail."
        "\n- Keine technischen Labels, keine HTML-Tags, keine FAQ-Kennzeichnung."
        "\n- Gib die Antwort so aus, dass sie direkt als E-Mail verschickt werden kann und sehr gut lesbar ist."
        "\n- Beispiel für gutes Format (bitte IMMER so antworten):\n"
        "\nHallo Max,\n\n"
        "vielen Dank für deine Anfrage. Hier die wichtigsten Schritte:\n"
        "1. Logge dich ein.\n2. Klicke auf ...\n3. Prüfe ...\n\nFalls du weitere Fragen hast, melde dich gerne!\n\nViele Grüße\nDein Support-Team\n"
        "\nE-Mails IMMER klar gegliedert mit Absätzen, Listen und Themenblöcken formatieren – keine Fließtexte! (email_formatting Regel)\n"
        "Führe niemals destructive Queries wie DROP, DELETE, UPDATE ohne explizite Freigabe aus!\n"
        "Antworte immer auf Deutsch.\n"
        f"Datenbankschema (Knowledge):\n{knowledge}\n"
        f"(Kanal: {channel})\n"
        f"Datenbank-Kontext: {db_context}\n"
    )
    # 0. Schritt: Intent bestimmen (nur Heuristik, kein LLM)
    intent = classify_intent(user_message)
    try:
        logging.info(f"[agent_respond] intent={intent} channel={channel}")
    except Exception:
        pass

    # Hilfsfunktionen
    def good_answer(text: str) -> bool:
        if not text:
            return False
        t = text.strip()
        if len(t) < 20:
            return False
        bad_tokens = ["nicht beantworten", "kann nicht helfen", "später erneut", "keine daten"]
        return not any(b in t.lower() for b in bad_tokens)

    def run_sql(query: str):
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return rows
        except Exception as e:
            import logging
            logging.error(f"[DB-Exception] Fehler bei DB-Abfrage: {e}")
            return None

    # 1. Schritt: FAQ-LangChain nutzen (nur wenn Intent 'faq')
    try:
        if intent == "faq":
            faq_resp = faq_answer(user_message)
            if faq_resp and len(faq_resp.strip()) > 10 and "nicht beantworten" not in faq_resp.lower():
                return faq_resp.strip()
    except Exception as e:
        logging.error(f"[FAQ-LangChain-Exception] Fehler bei der FAQ-Antwort für Frage '{user_message}': {e}")
    # 2. Schritt: Fallback auf OpenAI/DB wie gehabt
    import re
    import unicodedata
    def normalize(text):
        text = text.lower().strip()
        text = unicodedata.normalize('NFKD', text)
        text = re.sub(r'[\W_]+' , '', text)
        return text
    user_message_norm = normalize(user_message)
    user_message_lower = user_message.lower().strip()
    try:
        # Dynamische Token-Grenze: E-Mail braucht oft mehr Platz
        default_max = 900 if channel == "email" else 512
        try:
            env_max = int(os.environ.get("AGENT_MAX_TOKENS", str(default_max)))
        except Exception:
            env_max = default_max
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=env_max,
            temperature=0.2
        )
        antwort = response.choices[0].message.content.strip()
        # Eventuelle Code-Fences am Anfang/Ende entfernen
        import re as _re
        antwort = _re.sub(r'^```(?:html|\w+)?\s*', '', antwort)
        antwort = _re.sub(r'```\s*$', '', antwort)
        # Automatische Nachbearbeitung: E-Mail-Antworten schön formatieren
        if channel == "email" and antwort:
            import re
            # Keine Absätze nach Punkt in URL
            def absatz_sub(match):
                s = match.group(0)
                if 'http' in s or 'www.' in s:
                    return s
                return s[0] + '\n\n'
            # Nach jedem Satzende (Punkt, Ausrufezeichen, Fragezeichen, außer bei URLs) einen Absatz erzwingen
            antwort = re.sub(r'([.!?])\s+', absatz_sub, antwort)
            # Schrittanweisungen als Listenpunkt erkennen
            antwort = re.sub(r'(?i)\b(logge dich|klicke|scrolle|prüfe|beachte|falls|kontaktiere)\b', r'\n- \1', antwort)
            # Listenpunkte ("1. ...") jeweils in eigene Zeile
            antwort = re.sub(r'(\d+\. )', r'\n\1', antwort)
            antwort = re.sub(r'\n{3,}', '\n\n', antwort)
            # Immer mindestens zwei Absätze erzwingen
            if antwort.count('\n\n') < 2:
                antwort = antwort.replace('. ', '.\n\n')
            antwort = antwort.strip()


        # Wenn das LLM ein SQL-Statement zurückgibt, führe es aus (alle Kanäle) und formatiere die Ergebnisse
        sql_pattern = re.compile(r'^(SELECT|SHOW|DESCRIBE|WITH) ', re.IGNORECASE)
        if sql_pattern.match(antwort):
            rows = run_sql(antwort)
            if rows is None:
                # DB-Fehler -> Fallback FAQ (Retry) -> General
                try:
                    faq_retry = faq_answer(user_message)
                    if good_answer(faq_retry):
                        return faq_retry.strip()
                except Exception:
                    pass
                return "Entschuldigung, ich konnte dazu gerade keine Daten liefern. Wenn du magst, formuliere die Frage etwas anders oder gib mir mehr Kontext."
            if not rows:
                # Kein Ergebnis -> Fallback auf FAQ (Retry), dann General
                try:
                    faq_retry = faq_answer(user_message)
                    if good_answer(faq_retry):
                        return faq_retry.strip()
                except Exception:
                    pass
                # General LLM zweite Runde (mit klarem Hinweis vermeiden wir Loop)
                return "Es wurden keine passenden Daten gefunden. Vielleicht hilft dir Folgendes: \n\n- Prüfe das Datum oder die Schreibweise.\n- Stelle die Frage allgemeiner, z. B. ohne konkrete Namen."
            # Ergebnisse formatieren
            result_lines = []
            for row in rows:
                result_lines.append(", ".join(f"{k}: {v}" for k, v in row.items()))
            result_text = "\n".join(result_lines)
            return result_text
        # Qualitätscheck und Fallback-Kaskade
        if good_answer(antwort):
            return antwort
        # Wenn intent war 'db' aber Antwort nicht gut, probiere FAQ, dann General
        if intent == "db":
            try:
                faq_retry = faq_answer(user_message)
                if good_answer(faq_retry):
                    return faq_retry.strip()
            except Exception:
                pass
        # Generelle Antwort (zweite Runde vermeiden wir – wir geben hilfreichen Standardhinweis)
        return "Entschuldigung, ich habe dazu gerade keine perfekte Antwort gefunden. Hier ein allgemeiner Hinweis: Prüfe bitte unsere Hilfe/FAQ oder stelle die Frage etwas konkreter."
    except Exception as e:
        logging.error(f"[FAQ/DB-Exception] Fehler bei der Antwort für Frage '{user_message}': {e}")
        return "Entschuldigung, ich konnte deine Frage gerade nicht beantworten. Bitte versuche es später erneut oder kontaktiere den Support."
