-- Add reply preference fields to contacts table (Begrüßung/Abschluss + Stil-Slider)
-- Run this on your production database

ALTER TABLE contacts 
ADD COLUMN IF NOT EXISTS reply_greeting_template VARCHAR(255) DEFAULT NULL COMMENT 'Standard-Begrüßung für Antworten an diesen Kontakt',
ADD COLUMN IF NOT EXISTS reply_closing_template VARCHAR(255) DEFAULT NULL COMMENT 'Standard-Abschluss für Antworten an diesen Kontakt',
ADD COLUMN IF NOT EXISTS reply_length_level TINYINT DEFAULT NULL COMMENT '1-5: Antwortlänge (1=sehr kurz, 5=sehr lang)',
ADD COLUMN IF NOT EXISTS reply_formality_level TINYINT DEFAULT NULL COMMENT '1-5: Förmlichkeit (1=sehr locker, 5=sehr formell)',
ADD COLUMN IF NOT EXISTS reply_salutation_mode VARCHAR(10) DEFAULT NULL COMMENT 'du oder sie (falls gesetzt, überschreibt Auto)',
ADD COLUMN IF NOT EXISTS reply_persona_mode VARCHAR(10) DEFAULT NULL COMMENT 'ich oder wir (Perspektive der Antwort)',
ADD COLUMN IF NOT EXISTS reply_style_source VARCHAR(20) DEFAULT NULL COMMENT 'manual, history, type_default, global_default';
