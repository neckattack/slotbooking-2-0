import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_blue_db_connection():
    """
    Stellt eine Verbindung zur neckattack BLUE-Datenbank her.
    Die Zugangsdaten werden aus den Umgebungsvariablen gelesen.
    """
    return mysql.connector.connect(
        host=os.environ.get('BLUE_DB_HOST'),
        user=os.environ.get('BLUE_DB_USER'),
        password=os.environ.get('BLUE_DB_PASSWORD'),
        database=os.environ.get('BLUE_DB_NAME'),
        port=int(os.environ.get('BLUE_DB_PORT', 3306)),
        charset='utf8mb4',
        use_unicode=True
    )
