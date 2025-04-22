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
    data = request.get_json()
    user_msg = data.get('message', '').strip()
    if not user_msg:
        return jsonify({'error': 'Keine Nachricht erhalten.'}), 400

    # Beispiel: Bei bestimmten Schlüsselwörtern Datenbankabfrage machen
    db_info = ""
    if any(kw in user_msg.lower() for kw in ["termin", "slot", "buchung", "frei", "belegt"]):
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT date, id FROM dates ORDER BY date DESC LIMIT 5")
            termine = cursor.fetchall()
            db_info = f"Letzte Termine: {termine}"
            cursor.close()
            conn.close()
        except Exception as e:
            db_info = f"[DB-Fehler: {e}]"

    prompt = (
        "Du bist ein hilfreicher Assistent für Terminbuchungen. "
        "Wenn der Nutzer nach Terminen fragt, beantworte auf Basis folgender Datenbankinfos: "
        f"{db_info}\n"
        f"Nutzer: {user_msg}\nAssistent:"
    )
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Du bist ein Termin-Assistent."},
                      {"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message['content'].strip()
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
