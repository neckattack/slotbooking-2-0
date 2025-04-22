import pytest
from app import get_db_connection

def test_get_db_connection():
    """Testet, ob get_db_connection() eine funktionierende Verbindung liefert."""
    try:
        conn = get_db_connection()
        assert conn.is_connected()  # Für mysql-connector-python
        conn.close()
    except Exception as e:
        pytest.fail(f"get_db_connection() schlägt fehl: {e}")
