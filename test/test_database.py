import pytest
import mysql.connector
from dotenv import load_dotenv
import os

# Lade Umgebungsvariablen
load_dotenv()

def test_database_connection():
    """Test ob die Datenbankverbindung funktioniert"""
    try:
        # Verbindung zur Datenbank herstellen
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT')),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        
        # Prüfe ob die Verbindung aktiv ist
        assert connection.is_connected()
        
        # Schließe die Verbindung
        connection.close()
        
    except Exception as e:
        pytest.fail(f"Datenbankverbindung fehlgeschlagen: {str(e)}")

def test_termine_table():
    """Test ob die Termine-Tabelle existiert und die erwarteten Spalten hat"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT')),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        
        cursor = connection.cursor()
        
        # Prüfe ob die Tabelle existiert
        cursor.execute("SHOW TABLES LIKE 'termine'")
        assert cursor.fetchone() is not None, "Termine-Tabelle nicht gefunden"
        
        # Prüfe die Spalten
        cursor.execute("DESCRIBE termine")
        columns = [row[0] for row in cursor.fetchall()]
        expected_columns = ['id', 'datum', 'zeit', 'firma', 'kunde', 'kunde_email', 'masseur', 'masseur_email']
        for col in expected_columns:
            assert col in columns, f"Spalte {col} fehlt in der Tabelle"
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        pytest.fail(f"Tabellen-Test fehlgeschlagen: {str(e)}")
