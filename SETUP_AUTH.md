# Auth-System Setup

## 1. Datenbank: users-Tabelle anlegen

```sql
CREATE TABLE users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(320) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(16) DEFAULT 'user',
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  active BOOLEAN DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login DATETIME,
  KEY idx_email (email),
  KEY idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 2. Ersten Super-Admin erstellen

**Passwort für ersten User:** `admin123` (bitte später ändern!)

```sql
INSERT INTO users (email, password_hash, role, first_name, last_name, active)
VALUES (
  'deine@email.de',  -- HIER DEINE E-MAIL EINTRAGEN!
  '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYsF.LKqK9W',
  'superadmin',
  'Super',
  'Admin',
  TRUE
);
```

## 3. Umgebungsvariable: JWT_SECRET_KEY

**In .env einfügen:**

```bash
# JWT Secret (für Token-Signatur)
JWT_SECRET_KEY=7K9mP2nQ4rS6tU8vW0xY2zA3bC5dE7fG9hJ1kL3mN5oP7qR9sT1uV3wX5yZ7aB9c
```

## 4. Dependencies installieren

```bash
pip install PyJWT bcrypt
# oder
pip install -r requirements.txt
```

## 5. Server neu starten

```bash
# Gunicorn neu starten (je nach Setup):
systemctl restart inboxiq
# oder
killall gunicorn && gunicorn app:app -b 0.0.0.0:8000
```

## 6. Testen

1. Browser: https://inboxiq.eu/emails
2. Login-Modal erscheint automatisch
3. E-Mail + Passwort eingeben (`admin123`)
4. Bei Erfolg: Token wird in localStorage gespeichert
5. Inbox lädt automatisch

## Rollen-System

- **`user`** (Standard): Kann eigene E-Mails verwalten, eigene Settings ändern
- **`admin`**: Kann User-Verwaltung (später)
- **`superadmin`**: Kann alles + Terminverwaltung (BLUE-DB)

## Passwort ändern (später via UI)

Aktuell nur via SQL möglich:

```python
# Python-Script zum Hash generieren:
import bcrypt
password = "neues_passwort"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(hashed.decode('utf-8'))
```

Dann in SQL:
```sql
UPDATE users SET password_hash='NEUER_HASH' WHERE email='deine@email.de';
```
