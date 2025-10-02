-- Testdaten für zukünftige Termine (August/September 2025)
-- Ansprechpartner (admin)
INSERT INTO admin (id, first_name, last_name, email) VALUES
  (2001, 'Anna', 'Alpha', 'anna.alpha@testfirma.de'),
  (2002, 'Ben', 'Beta', 'ben.beta@testfirma.de')
  ON DUPLICATE KEY UPDATE first_name=VALUES(first_name), last_name=VALUES(last_name), email=VALUES(email);

-- Firmen/Clients
INSERT INTO clients (id, name, contact_client_id) VALUES (1001, 'Testfirma Alpha', 2001), (1002, 'Testfirma Beta', 2002)
  ON DUPLICATE KEY UPDATE name=VALUES(name), contact_client_id=VALUES(contact_client_id);

-- Termine (dates) für 2 Firmen, je 2 Tage
INSERT INTO dates (id, client_id, date, masseur_id) VALUES
  (3001, 1001, '2025-08-10', 2001), (3002, 1001, '2025-08-11', 2001),
  (3003, 1002, '2025-09-05', 2002), (3004, 1002, '2025-09-06', 2002)
  ON DUPLICATE KEY UPDATE client_id=VALUES(client_id), date=VALUES(date), masseur_id=VALUES(masseur_id);

-- Zeitslots (times) je Tag (4 Slots pro Tag)
INSERT INTO times (id, date_id, time_start, time_end) VALUES
  (4001, 3001, '09:00', '09:30'), (4002, 3001, '09:30', '10:00'), (4003, 3001, '10:00', '10:30'), (4004, 3001, '10:30', '11:00'),
  (4005, 3002, '09:00', '09:30'), (4006, 3002, '09:30', '10:00'), (4007, 3002, '10:00', '10:30'), (4008, 3002, '10:30', '11:00'),
  (4009, 3003, '09:00', '09:30'), (4010, 3003, '09:30', '10:00'), (4011, 3003, '10:00', '10:30'), (4012, 3003, '10:30', '11:00'),
  (4013, 3004, '09:00', '09:30'), (4014, 3004, '09:30', '10:00'), (4015, 3004, '10:00', '10:30'), (4016, 3004, '10:30', '11:00')
  ON DUPLICATE KEY UPDATE date_id=VALUES(date_id), time_start=VALUES(time_start), time_end=VALUES(time_end);

-- Buchungen (reservations): einige gebucht, einige frei, einige "Pause"
INSERT INTO reservations (id, time_id, name, email) VALUES
  (5001, 4001, 'Max Mustermann', 'max@testkunde.de'),
  (5002, 4002, 'Pause', 'pause@testkunde.de'),
  (5003, 4003, 'Erika Beispiel', 'erika@example.com'),
  (5004, 4005, '---', NULL),
  (5005, 4007, 'Pause', 'irgendwasPAUSE@firma.de'),
  (5006, 4009, 'Klaus Kunde', 'klaus@kunde.de'),
  (5007, 4010, '---', NULL),
  (5008, 4011, 'Urlaub', 'pause@urlaub.de'),
  (5009, 4014, 'Julia Demo', 'julia@demo.de')
  ON DUPLICATE KEY UPDATE time_id=VALUES(time_id), name=VALUES(name), email=VALUES(email);
