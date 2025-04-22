import os
from flask import Flask, render_template, request, jsonify
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime
import openai

load_dotenv()

app = Flask(__name__)

import logging
app.logger.setLevel(logging.INFO)

# Logge die Version des MySQL-Connectors
import mysql.connector
app.logger.info(f"mysql-connector-python Version: {mysql.connector.__version__}")

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT", 3306))
    )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/termine")
def termine():
    datum = request.args.get("datum")
    if not datum:
        return jsonify({"error": "Kein Datum angegeben"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        r.id AS reservierungs_id,
        r.name AS kunde,
        r.email AS kunde_email,
        t.id AS time_id,
        t.time_start,
        t.time_end,
        d.id AS datum_id,
        d.date,
        c.name AS firma,
        a1.first_name AS masseur_vorname,
        a1.last_name AS masseur_nachname,
        a1.email AS masseur_email,
        a2.first_name AS kontakt_vorname,
        a2.last_name AS kontakt_nachname,
        a2.email AS kontakt_email
    FROM dates d
    JOIN times t ON t.date_id = d.id
    LEFT JOIN reservations r ON r.time_id = t.id
    JOIN clients c ON d.client_id = c.id
    LEFT JOIN admin a1 ON d.masseur_id = a1.id
    LEFT JOIN admin a2 ON c.contact_masseur_id = a2.id
    WHERE d.date = %s
    ORDER BY t.time_start
    """
    cursor.execute(sql, (datum,))
    result = cursor.fetchall()
    termine = []
    for row in result:
        masseur = (
            f"{row['masseur_vorname']} {row['masseur_nachname']}"
            if row['masseur_vorname'] else
            f"{row['kontakt_vorname']} {row['kontakt_nachname']}"
            if row['kontakt_vorname'] else "Kein Masseur zugewiesen"
        )
        masseur_email = (
            row['masseur_email'] if row['masseur_email'] else row['kontakt_email']
        )
        termine.append({
            "zeit": f"{row['time_start']} - {row['time_end']}",
            "kunde": row['kunde'],
            "kunde_email": row['kunde_email'],
            "firma": row['firma'],
            "masseur": masseur,
            "masseur_email": masseur_email,
            "reservierungs_id": row['reservierungs_id'],
            "time_id": row['time_id']  # Wichtig für das Löschen
        })
    cursor.close()
    conn.close()
    return jsonify(termine)

@app.route("/api/termine/delete", methods=["POST"])
def delete_termine():
    if not request.is_json:
        return jsonify({"error": "Content-Type muss application/json sein"}), 400
    
    termine = request.get_json()
    if not isinstance(termine, list):
        return jsonify({"error": "Ungültiges Format"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # DEBUG: Alle Zeitslots für jedes angeforderte Datum und jede Firma (inkl. Buchungsstatus)
    # (Mehrfache Firmen/Datums-Kombis werden mehrfach geloggt, aber das ist für Debug-Zwecke okay)
    for termin in termine:
        firma = termin.get("firma")
        datum = termin.get("datum")
        if not (firma and datum):
            continue
        cursor.execute(
            """
            SELECT t.time_start, t.id, r.id as reservation_id
            FROM times t
            JOIN dates d ON t.date_id = d.id
            JOIN clients c ON d.client_id = c.id
            LEFT JOIN reservations r ON r.time_id = t.id
            WHERE d.date = %s AND c.name = %s
            ORDER BY t.time_start
            """, (datum, firma)
        )
        slots = cursor.fetchall()
        # DEBUG: Alle Zeitslots für das angeforderte Datum und die Firma (explizit für den User-Check)
        cursor.execute(
            "SELECT t.time_start, t.id, r.id as reservation_id "
            "FROM times t "
            "JOIN dates d ON t.date_id = d.id "
            "JOIN clients c ON d.client_id = c.id "
            "LEFT JOIN reservations r ON r.time_id = t.id "
            "WHERE d.date = %s AND c.name = %s ",
            (datum, firma)
        )
        all_slots = cursor.fetchall()
        for row in all_slots:
            zeit = str(row[0])
            time_id = row[1]
            reserv_id = row[2]
            status = "frei" if reserv_id is None else "belegt"
            app.logger.info(f"Slot: {zeit} (time_id: {time_id}) - {status}")
        app.logger.info(f"[DEBUG-USER] Alle Slots für {datum}, {firma}: {[ (str(row[0]), row[1], row[2]) for row in all_slots ]}")
    
    try:
        # Hole und lösche Zeitslots für das gegebene Datum, die Firma und die exakte Zeit
        # Teste alternative Parameter-Syntax (named style)
        sql_select_named = (
            "SELECT t.id "
            "FROM times t "
            "JOIN dates d ON t.date_id = d.id "
            "JOIN clients c ON d.client_id = c.id "
            "LEFT JOIN reservations r ON r.time_id = t.id "
            "WHERE d.date = %(datum)s "
            "AND c.name = %(firma)s "
            "AND TIME_TO_SEC(t.time_start) = %(zeit_seconds)s "
            "AND r.id IS NULL"
        )
        app.logger.info(f"SQL-Statement (named, nur freie Slots, Zeit in Sekunden): {sql_select_named}")

        sql_delete = "DELETE FROM times WHERE id = %s"
        deleted_count = 0

        for termin in termine:
            firma = termin.get("firma")
            zeit_intervall = termin.get("zeit") or termin.get("time")
            zeit_start = zeit_intervall.split(" - ")[0].strip() if zeit_intervall and " - " in zeit_intervall else zeit_intervall
            datum = termin.get("datum")

            # Zeit in Sekunden seit Mitternacht umwandeln
            try:
                h, m, s = map(int, zeit_start.split(":"))
                zeit_seconds = h * 3600 + m * 60 + s
            except Exception as e:
                app.logger.error(f"Zeit-Parsing-Fehler für '{zeit_start}': {e}")
                continue

            param_dict = {"datum": datum, "firma": firma, "zeit_seconds": zeit_seconds}
            app.logger.info(f"Parameter-Typ: {type(param_dict)}, Keys: {list(param_dict.keys())}")
            app.logger.info(f"Parameter-Werte: datum={datum}, firma={firma}, zeit_start={zeit_start}, zeit_seconds={zeit_seconds}")

            if not all([firma, zeit_start, datum]):
                app.logger.warning(f"Ungültige Termin-Daten (werden übersprungen): {termin}")
                continue

            app.logger.info(f"Lösche Termin: firma={firma}, zeit_start={zeit_start} ({zeit_seconds}s), datum={datum}")
            try:
                cursor.execute(sql_select_named, param_dict)
                result = cursor.fetchone()
                app.logger.info(f"SQL-Select-Result für {param_dict}: {result}")
            except Exception as e:
                app.logger.error(f"SQL-Fehler bei execute: {e}")
                continue

            if result:
                cursor.execute(sql_delete, (result[0],))
                deleted_count += 1
        
        conn.commit()
        return jsonify({
            "message": f"{deleted_count} Termine wurden erfolgreich gelöscht",
            "deleted_count": deleted_count
        })
        
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Fehler beim Löschen der Termine: {str(e)}")
        return jsonify({"error": str(e)}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route("/api/slots")
def slots():
    datum = request.args.get("datum")
    if not datum:
        return jsonify({"error": "Kein Datum angegeben"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Hole alle Firmen (clients) für das Datum
    sql_clients = """
        SELECT d.id as date_id, c.id as client_id, c.name as firma
        FROM dates d
        JOIN clients c ON d.client_id = c.id
        WHERE d.date = %s
    """
    cursor.execute(sql_clients, (datum,))
    client_rows = cursor.fetchall()

    result = []
    for client in client_rows:
        date_id = client['date_id']
        firma = client['firma']
        # Hole alle Slots für diese date_id
        sql_slots = """
            SELECT t.id as time_id, t.time_start, r.id as reservierungs_id, r.name as kunde, r.email as kunde_email
            FROM times t
            LEFT JOIN reservations r ON r.time_id = t.id
            WHERE t.date_id = %s
            ORDER BY t.time_start
        """
        cursor.execute(sql_slots, (date_id,))
        slots = []
        for row in cursor.fetchall():
            slots.append({
                "time_id": row['time_id'],
                "time_start": str(row['time_start']),
                "frei": row['reservierungs_id'] is None,
                "kunde": row['kunde'] if row['kunde'] else None,
                "kunde_email": row['kunde_email'] if row['kunde_email'] else None
            })
        result.append({
            "firma": firma,
            "date_id": date_id,
            "slots": slots
        })
    cursor.close()
    conn.close()
    return jsonify(result)

# --- ChatGPT-API-Endpunkt ---
@app.route('/api/chat', methods=['POST'])
def chat_api():
    import re
    data = request.get_json()
    messages = data.get('messages', [])
    if not messages or not isinstance(messages, list):
        return jsonify({'error': 'Kein Nachrichtenverlauf erhalten.'}), 400

    # --- Dynamische Kontext-Erweiterung für gezielte Fragen ---
    # Prüfe, ob letzte User-Nachricht nach bestimmten Mustern fragt
    db_context = ""
    last_user_msg = None
    for m in reversed(messages):
        if m.get('role') == 'user':
            last_user_msg = m.get('content', '')
            break
    from datetime import datetime, timedelta
    import pytz
    berlin = pytz.timezone('Europe/Berlin')
    now_berlin = datetime.now(berlin)
    today_str = now_berlin.strftime('%Y-%m-%d')

    name_match = None
    firmen_fuer_datum = None
    antwort_datum = None
    next_termin_name = None
    if last_user_msg:
        # Suche nach Mustern wie "letzter Termin von ..." oder "Wann war der letzte Termin von ..."
        match = re.search(r'letzte[rn]? termin (von|für) ([\w\s.\-]+)', last_user_msg, re.IGNORECASE)
        if not match:
            match = re.search(r'wann war der letzte termin (von|für) ([\w\s.\-]+)', last_user_msg, re.IGNORECASE)
        if match:
            name_match = match.group(2).strip()
        # Nächster Termin für ...
        match_next = re.search(r'nächste[rsn]? termin (von|für) ([\w\s.\-]+)', last_user_msg, re.IGNORECASE)
        if not match_next:
            match_next = re.search(r'wann.*nächste[rsn]? termin (von|für) ([\w\s.\-]+)', last_user_msg, re.IGNORECASE)
        if match_next:
            next_termin_name = match_next.group(2).strip()
        # Firmen mit Terminen an einem bestimmten Tag
        match_firmen = re.search(r'firmen.*(morgen|am ([0-9]{1,2})[.\-/]([0-9]{1,2})[.\-/]([0-9]{2,4}))', last_user_msg, re.IGNORECASE)
        if match_firmen:
            if 'morgen' in match_firmen.group(1).lower():
                antwort_datum = (now_berlin + timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                # Versuche, ein Datum zu extrahieren
                try:
                    tag, monat, jahr = match_firmen.group(2), match_firmen.group(3), match_firmen.group(4)
                    if len(jahr) == 2:
                        jahr = '20' + jahr
                    antwort_datum = f"{jahr}-{monat.zfill(2)}-{tag.zfill(2)}"
                except Exception:
                    antwort_datum = None
            if antwort_datum:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("""
                        SELECT DISTINCT firma FROM termine WHERE datum = %s
                    """, (antwort_datum,))
                    firmen = [row['firma'] for row in cursor.fetchall() if row.get('firma')]
                    if firmen:
                        db_context += f" Firmen mit Termin am {antwort_datum}: {', '.join(firmen)}."
                    else:
                        db_context += f" Für {antwort_datum} wurden keine Firmen mit Terminen gefunden."
                    cursor.close()
                    conn.close()
                except Exception as e:
                    db_context += f" [DB-Fehler bei Firmenabfrage: {e}]"
    if next_termin_name:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT MIN(datum) as naechster_termin, kunde FROM termine
                WHERE kunde LIKE %s AND datum >= %s
            """, (f"%{next_termin_name}%", today_str))
            row = cursor.fetchone()
            if row and row['naechster_termin']:
                db_context += f" Nächster Termin für {next_termin_name}: {row['naechster_termin']}."
            else:
                db_context += f" Für {next_termin_name} wurde kein zukünftiger Termin gefunden."
            cursor.close()
            conn.close()
        except Exception as e:
            db_context += f" [DB-Fehler: {e}]"
    elif name_match:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT MAX(datum) as letzter_termin, kunde
                FROM termine
                WHERE kunde LIKE %s
            """, (f"%{name_match}%",))
            row = cursor.fetchone()
            if row and row['letzter_termin']:
                db_context += f" Letzter Termin für {name_match}: {row['letzter_termin']}."
            else:
                db_context += f" Für {name_match} wurde kein Termin gefunden."
            cursor.close()
            conn.close()
        except Exception as e:
            db_context += f" [DB-Fehler: {e}]"
    # --- System-Prompt klarstellen ---
    system_prompt = (
        f"Du bist ein KI-Assistent für Terminbuchungen. Das heutige Datum ist {today_str} (Europe/Berlin). "
        "Du hast Zugriff auf die aktuelle Datenbank und bekommst bei jeder Nutzerfrage die relevanten Daten im Kontext übermittelt. "
        "Nutze diese Daten, um die Nutzerfrage korrekt und freundlich zu beantworten. Antworte niemals, dass du keinen Zugriff auf Daten hast. "
        "Wenn keine passenden Daten gefunden wurden, erkläre das höflich."
    )
    if db_context:
        system_prompt += f" Datenbank-Info: {db_context}"
    # Ersetze die erste system-Nachricht im Verlauf (falls vorhanden), sonst füge sie vorn an
    new_messages = messages[:]
    found_system = False
    for i, m in enumerate(new_messages):
        if m.get('role') == 'system':
            new_messages[i]['content'] = system_prompt
            found_system = True
            break
    if not found_system:
        new_messages = [{'role': 'system', 'content': system_prompt}] + new_messages
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=new_messages
        )
        answer = response.choices[0].message['content'].strip()
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
