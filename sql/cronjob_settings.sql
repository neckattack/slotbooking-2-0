-- Tabelle für Cronjob-Einstellungen
CREATE TABLE IF NOT EXISTS cronjob_settings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    interval ENUM('daily', 'weekly', 'monthly') NOT NULL DEFAULT 'daily',
    time TIME NOT NULL DEFAULT '02:00:00',
    weekday INT NULL, -- 0=Montag, 6=Sonntag (nur für weekly)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
