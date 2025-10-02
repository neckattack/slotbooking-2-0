-- Fügt einen UNIQUE-Constraint auf time_id in reservations hinzu (verhindert Doppelbuchungen)
ALTER TABLE reservations
ADD CONSTRAINT unique_time_id UNIQUE (time_id);
