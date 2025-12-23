-- Migration: Kontakt-Themen-Mapping und Gesamtprofil-Feld

-- 1) Neues Feld für Langprofil in contacts
ALTER TABLE contacts
  ADD COLUMN profile_summary_full MEDIUMTEXT NULL AFTER profile_summary;

-- 2) Zuordnungstabelle: welche E-Mails gehören zu welchem Thema?
--    Jede E-Mail kann mehreren Themen zugeordnet sein, jedes Thema mehreren E-Mails.
CREATE TABLE IF NOT EXISTS contact_topic_emails (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_email VARCHAR(255) NOT NULL,
  contact_id INT NOT NULL,
  topic_id INT NOT NULL,
  email_id INT NOT NULL,
  match_score FLOAT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_cte_user_contact_topic (user_email, contact_id, topic_id),
  KEY idx_cte_email (email_id),
  CONSTRAINT fk_cte_topic FOREIGN KEY (topic_id) REFERENCES contact_topics(id) ON DELETE CASCADE,
  CONSTRAINT fk_cte_email FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
