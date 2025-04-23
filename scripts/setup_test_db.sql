-- Komplettes Setup für Slotbooking-Testdatenbank

-- Reihenfolge: reservations hängt von times, times von dates, dates von clients, admin ist unabhängig

DROP TABLE IF EXISTS reservations;
DROP TABLE IF EXISTS times;
DROP TABLE IF EXISTS dates;
DROP TABLE IF EXISTS clients;
DROP TABLE IF EXISTS admin;

CREATE TABLE clients (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE dates (
    id INT PRIMARY KEY AUTO_INCREMENT,
    date DATE NOT NULL,
    client_id INT,
    masseur_id INT,
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (masseur_id) REFERENCES admin(id)
);

CREATE TABLE times (
    id INT PRIMARY KEY AUTO_INCREMENT,
    date_id INT,
    time_start TIME NOT NULL,
    time_end TIME NOT NULL,
    FOREIGN KEY (date_id) REFERENCES dates(id)
);

CREATE TABLE admin (
    id INT PRIMARY KEY AUTO_INCREMENT,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    contact_masseur_id INT,
    FOREIGN KEY (contact_masseur_id) REFERENCES admin(id)
);

CREATE TABLE reservations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    time_id INT,
    name VARCHAR(255),
    email VARCHAR(255),
    FOREIGN KEY (time_id) REFERENCES times(id)
);

-- Beispiel-Admins
INSERT INTO admin (first_name, last_name, email) VALUES
('Anna', 'Masseur', 'anna.masseur@example.com'),
('Bernd', 'Kontakt', 'bernd.kontakt@example.com');

-- Beispiel-Clients
INSERT INTO clients (name) VALUES ('Firma Alpha'), ('Firma Beta');

-- Beispiel-Dates (je ein Tag pro Firma, mit Masseuren)
INSERT INTO dates (date, client_id, masseur_id) VALUES
('2025-04-24', 1, 1),
('2025-04-25', 2, 2);

-- Beispiel-Times (pro Tag mehrere Slots)
INSERT INTO times (date_id, time_start, time_end) VALUES
(1, '09:00', '10:00'),
(1, '10:00', '11:00'),
(2, '09:00', '10:00');

-- Beispiel-Reservations (ein Slot gebucht)
INSERT INTO reservations (time_id, name, email) VALUES
(2, 'Max Mustermann', 'max@example.com');
