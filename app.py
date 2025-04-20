import os
from flask import Flask, render_template, request, jsonify
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime

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
    
    try:
        # Hole und lösche Zeitslots für das gegebene Datum, die Firma und die exakte Zeit
        # Teste alternative Parameter-Syntax (named style)
        sql_select_named = (
            "SELECT t.id "
            "FROM times t "
            "JOIN dates d ON t.date_id = d.id "
            "JOIN clients c ON d.client_id = c.id "
            "WHERE d.date = %(datum)s "
            "AND c.name = %(firma)s "
            "AND TIME_FORMAT(t.time_start, '%H:%i:%s') = %(zeit)s"
        )
        app.logger.info(f"SQL-Statement (named): {sql_select_named}")

        # Test: Minimaler Query mit festen Werten (named)
        try:
            test_sql_named = "SELECT t.id FROM times t JOIN dates d ON t.date_id = d.id JOIN clients c ON d.client_id = c.id WHERE d.date = %(datum)s AND c.name = %(firma)s AND TIME_FORMAT(t.time_start, '%H:%i:%s') = %(zeit)s"
            test_params_named = {"datum": "2025-04-16", "firma": "BMDV Bundesministerium für Digitales und Verkehr", "zeit": "10:00:00"}
            app.logger.info(f"Test-Minimal-SQL (named): {test_sql_named}")
            app.logger.info(f"Test-Minimal-Params (named): {test_params_named}")
            cursor.execute(test_sql_named, test_params_named)
            test_result_named = cursor.fetchone()
            app.logger.info(f"Test-Minimal-Result (named): {test_result_named}")
        except Exception as e:
            app.logger.error(f"Test-Minimal-Query-Fehler (named): {e}")

        # Für die eigentliche Schleife: auch named style verwenden
        sql_delete = "DELETE FROM times WHERE id = %s"
        deleted_count = 0
        
        sql_delete = "DELETE FROM times WHERE id = %s"
        deleted_count = 0
        
        # Test-Query mit festen Werten (Debugging)
        test_params = ("2025-04-16", "BMDV Bundesministerium für Digitales und Verkehr", "10:00:00")
        app.logger.info(f"Test-Query mit: {test_params}")
        try:
            cursor.execute(sql_select, test_params)
            test_result = cursor.fetchone()
            app.logger.info(f"Test-Result: {test_result}")
        except Exception as e:
            app.logger.error(f"Test-Query-Fehler: {e}")

        for termin in termine:
            firma = termin.get("firma")
            time = termin.get("time")
            datum = termin.get("datum")

            # Logge Typen und Werte der Parameter
            param_dict = {"datum": datum, "firma": firma, "zeit": time}
            app.logger.info(f"Parameter-Typ: {type(param_dict)}, Keys: {list(param_dict.keys())}")
            app.logger.info(f"Parameter-Werte: datum={datum}, firma={firma}, time={time}")

            if not all([firma, time, datum]):
                app.logger.warning(f"Ungültige Termin-Daten (werden übersprungen): {termin}")
                continue

            app.logger.info(f"Lösche Termin: firma={firma}, time={time}, datum={datum}")
            try:
                cursor.execute(sql_select_named, param_dict)
                result = cursor.fetchone()
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

if __name__ == "__main__":
    app.run(debug=True)
