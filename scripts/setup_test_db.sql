-- Testdatenbank und User für Slotbooking-Testumgebung
CREATE DATABASE IF NOT EXISTS slotbooking_test DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'testuser'@'localhost' IDENTIFIED BY 'testpass';
GRANT ALL PRIVILEGES ON slotbooking_test.* TO 'testuser'@'localhost';
FLUSH PRIVILEGES;

-- Tabellenstruktur (nur Beispiel! Passe ggf. an dein Modell an)
-- Kopiere hier das CREATE TABLE für 'slots' aus deiner Produktivdatenbank!
-- Beispiel:
--
-- CREATE TABLE slots (
--   id INT NOT NULL,
--   datum DATE NOT NULL,
--   status VARCHAR(20),
--   kunde VARCHAR(255),
--   email VARCHAR(255),
--   PRIMARY KEY (id, datum)
-- );
