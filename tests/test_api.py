import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def use_test_db(monkeypatch):
    # Setze Umgebungsvariablen für eine Test-DB (NICHT Produktiv-DB!)
    monkeypatch.setenv("DB_HOST", os.environ.get("DB_TEST_HOST", "localhost"))
    monkeypatch.setenv("DB_USER", os.environ.get("DB_TEST_USER", "testuser"))
    monkeypatch.setenv("DB_PASSWORD", os.environ.get("DB_TEST_PASSWORD", "testpass"))
    monkeypatch.setenv("DB_NAME", os.environ.get("DB_TEST_NAME", "testdb"))
    monkeypatch.setenv("DB_PORT", os.environ.get("DB_TEST_PORT", "3306"))

import mysql.connector

@pytest.fixture
def client(monkeypatch):
    use_test_db(monkeypatch)
    app.config['TESTING'] = True
    # Setup: Testdaten anlegen
    setup_testdata()
    with app.test_client() as client:
        yield client
    # Teardown: Testdaten löschen
    teardown_testdata()

TEST_DATUM = "2099-01-01"
TEST_SLOT_ID = 9999999

def setup_testdata():
    # Lege einen Dummy-Slot für das Testdatum an
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT", 3306))
    )
    cur = conn.cursor()
    # Passe ggf. die Tabellennamen/Spalten an dein Modell an!
    cur.execute("""
        INSERT IGNORE INTO slots (id, datum, status, kunde, email)
        VALUES (%s, %s, 'frei', NULL, NULL)
    """, (TEST_SLOT_ID, TEST_DATUM))
    conn.commit()
    cur.close()
    conn.close()

def teardown_testdata():
    # Lösche den Dummy-Slot wieder
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT", 3306))
    )
    cur = conn.cursor()
    cur.execute("DELETE FROM slots WHERE id = %s AND datum = %s", (TEST_SLOT_ID, TEST_DATUM))
    conn.commit()
    cur.close()
    conn.close()

# --- Index-Route ---
def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Termine" in resp.data

# --- /api/slots ---
def test_slots_valid(client):
    resp = client.get("/api/slots?datum=2099-01-01")
    assert resp.status_code == 200 or resp.status_code == 400
    if resp.status_code == 200:
        data = resp.get_json()
        assert isinstance(data, list)

def test_slots_invalid(client):
    resp = client.get("/api/slots")  # fehlt das Datum
    assert resp.status_code in (400, 500)

# --- /api/termine ---
def test_termine_valid(client):
    resp = client.get("/api/termine?datum=2099-01-01")
    assert resp.status_code == 200 or resp.status_code == 400
    if resp.status_code == 200:
        data = resp.get_json()
        assert isinstance(data, list)

def test_termine_invalid(client):
    resp = client.get("/api/termine")  # fehlt das Datum
    assert resp.status_code in (400, 500)

# --- /api/termine/delete ---
def test_delete_termine_valid(client):
    # Sende eine leere Liste, das sollte zumindest 200 oder 400 ergeben, aber kein 500
    resp = client.post("/api/termine/delete", json=[])
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert "error" in data or "deleted_count" in data

def test_delete_termine_invalid_content_type(client):
    # Kein JSON gesendet
    resp = client.post("/api/termine/delete", data="notjson", content_type="text/plain")
    assert resp.status_code in (400, 500)

def test_delete_termine_invalid_format(client):
    # Sende absichtlich ungültiges Format
    resp = client.post("/api/termine/delete", json={"foo": "bar"})
    assert resp.status_code in (400, 500)
    data = resp.get_json()
    assert "error" in data

def test_db_connection(client):
    # Testet, ob die DB-Verbindung grundsätzlich klappt
    response = client.get(f"/api/slots?datum={TEST_DATUM}")
    assert response.status_code == 200

def test_slots_endpoint(client):
    # Testet, ob /api/slots den Dummy-Slot zurückgibt
    response = client.get(f'/api/slots?datum={TEST_DATUM}')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert any(slot.get('id') == TEST_SLOT_ID for slot in data)

def test_delete_termine(client):
    # Lösche gezielt den Dummy-Slot
    dummy_termine = [{"id": TEST_SLOT_ID, "datum": TEST_DATUM}]
    response = client.post('/api/termine/delete',
                          data=json.dumps(dummy_termine),
                          content_type='application/json')
    assert response.status_code == 200
    data = response.get_json()
    assert 'deleted_count' in data
    # Prüfe, dass der Slot wirklich gelöscht ist
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT", 3306))
    )
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM slots WHERE id = %s AND datum = %s", (TEST_SLOT_ID, TEST_DATUM))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    assert count == 0

# --- Optional: Test für Startseite (Design sichtbar) ---
def test_index_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Termine" in response.data  # Überschrift oder markantes Element
