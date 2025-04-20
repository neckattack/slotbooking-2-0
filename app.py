import os
from flask import Flask, render_template, request, jsonify
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

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
        # Hole alle Zeitslots für das gegebene Datum
        sql_select = """
        SELECT t.id, t.time_start, c.name
        FROM times t
        JOIN dates d ON t.date_id = d.id
        JOIN clients c ON d.client_id = c.id
        WHERE d.date = %s AND c.name = %s
        """
        
        # Lösche die Zeitslots
        sql_delete = "DELETE FROM times WHERE id = %s"
        
        deleted_count = 0
        for termin in termine:
            firma = termin.get("firma")
            time = termin.get("time")
            if not firma or not time:
                continue
                
            # Suche den passenden Zeitslot
            cursor.execute(sql_select, (datetime.now().strftime("%Y-%m-%d"), firma))
            slots = cursor.fetchall()
            
            # Finde den passenden Slot und lösche ihn
            for slot in slots:
                if slot[1].strftime("%H:%M:%S") == time:
                    cursor.execute(sql_delete, (slot[0],))
                    deleted_count += 1
                    break
        
        conn.commit()
        return jsonify({
            "message": f"{deleted_count} Termine wurden erfolgreich gelöscht",
            "deleted_count": deleted_count
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)
