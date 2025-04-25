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
        msg_lc = user_message.lower()
        # Schlüsselwörter für Terminabfragen
        termin_keywords = ["termin", "anmeldung", "buchung", "slot", "reservierung"]
        masseur_keywords = ["masseur", "wer ist morgen", "eingeteilt", "nächste(r|s)? termin", "kunde für masseur"]
        # 1. Flexible Terminabfrage
        if any(kw in msg_lc for kw in termin_keywords):
            # Datum erkennen
            if "morgen" in msg_lc:
                from datetime import timedelta
                datum = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                datum_nice = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
            else:
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
                    # Kein Datum erkannt: Rückfrage
                    return "Hallo,\n\nfür welches Datum möchtest du die Termine oder Anmeldungen wissen? Bitte gib das Datum an (z.B. 'am 25.04.2025').\n\nViele Grüße\nIhr neckattack-Team"
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
        # 2. Flexible Masseur-Abfragen
        elif any(re.search(kw, msg_lc) for kw in masseur_keywords):
            # Wer ist morgen eingeteilt?
            if "wer ist morgen" in msg_lc or ("masseur" in msg_lc and "morgen" in msg_lc):
                from datetime import timedelta
                datum = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                datum_nice = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor(dictionary=True)
                    sql = """
                        SELECT DISTINCT a.first_name, a.last_name, a.email
                        FROM dates d
                        JOIN admin a ON d.masseur_id = a.id
                        WHERE d.date = %s
                    """
                    cursor.execute(sql, (datum,))
                    rows = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    if not rows:
                        return f"Hallo,\n\nam {datum_nice} ist kein Masseur eingeteilt.\n\nViele Grüße\nIhr neckattack-Team"
                    masseure = [f"{row['first_name']} {row['last_name']} ({row['email']})" for row in rows]
                    return f"Hallo,\n\nam {datum_nice} sind folgende Masseure eingeteilt:\n" + "\n".join(masseure) + "\n\nViele Grüße\nIhr neckattack-Team"
                except Exception as e:
                    return f"Hallo,\n\nes gab einen Fehler bei der Masseur-Abfrage: {e}\n\nViele Grüße\nIhr neckattack-Team"
            # Nächster Termin/Kunde für Masseur XY
            # Erkenne auch "Wann hat Masseur XY einen Termin" oder "Wann ist Masseur XY gebucht"
            match = re.search(r'masseur(?:in)? ([a-zA-Zäöüß]+)', msg_lc)
            if match or re.search(r'wann.*masseur.*([a-zA-Zäöüß]+).*termin', msg_lc) or re.search(r'gebucht.*masseur.*([a-zA-Zäöüß]+)', msg_lc):
                if match:
                    masseur_name = match.group(1)
                else:
                    # Versuche den Namen aus anderen Formulierungen zu extrahieren
                    m2 = re.search(r'(?:wann|gebucht).*masseur.*([a-zA-Zäöüß]+)', msg_lc)
                    masseur_name = m2.group(1) if m2 else None
                if not masseur_name:
                    return "Hallo,\n\nBitte gib den Namen des Masseurs an, für den du die Termine wissen möchtest (z.B. 'Wann hat Masseur Müller einen Termin?').\n\nViele Grüße\nIhr neckattack-Team"
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor(dictionary=True)
                    sql = """
                        SELECT d.date, t.time_start, t.time_end, r.name AS kunde, r.email AS kunde_email
                        FROM dates d
                        JOIN admin a ON d.masseur_id = a.id
                        JOIN times t ON t.date_id = d.id
                        LEFT JOIN reservations r ON r.time_id = t.id
                        WHERE (a.first_name LIKE %s OR a.last_name LIKE %s)
                          AND d.date >= CURDATE()
                        ORDER BY d.date, t.time_start
                    """
                    cursor.execute(sql, (f"%{masseur_name}%", f"%{masseur_name}%"))
                    rows = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    if not rows:
                        return f"Hallo,\n\nFür Masseur {masseur_name} sind keine kommenden Termine im System eingetragen.\n\nViele Grüße\nIhr neckattack-Team"
                    antwort = f"Hallo,\n\nHier sind alle kommenden Termine für Masseur {masseur_name}:\n"
                    for row in rows:
                        antwort += f"- {row['date']} {row['time_start']}-{row['time_end']}: {row['kunde'] or 'FREI'}"
                        if row['kunde_email']:
                            antwort += f" ({row['kunde_email']})"
                        antwort += "\n"
                    antwort += "\nViele Grüße\nIhr neckattack-Team"
                    return antwort
                except Exception as e:
                    return f"Hallo,\n\nes gab einen Fehler bei der Masseur-Terminabfrage: {e}\n\nViele Grüße\nIhr neckattack-Team"
            return "Hallo,\n\nBitte gib den Namen des Masseurs an, für den du die Termine wissen möchtest (z.B. 'Wann hat Masseur Müller einen Termin?').\n\nViele Grüße\nIhr neckattack-Team"
        # 3. Sonstige Fragen
        else:
            return "Hallo,\n\nBitte stelle eine konkrete Frage zu Terminen, Anmeldungen oder Masseuren, damit ich dir weiterhelfen kann.\n\nViele Grüße\nIhr neckattack-Team"

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
