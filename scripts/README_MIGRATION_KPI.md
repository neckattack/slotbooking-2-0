# KPI-Felder Migration

## Wichtig: Vor dem Push auf Render ausführen!

Diese Migration fügt neue KPI-Felder zur `contacts` Tabelle hinzu.

## SQL ausführen auf Render:

1. Gehe zu Render Dashboard
2. Öffne deine MySQL Database
3. Öffne den MySQL Shell/Query Editor
4. Führe das Script `add_contact_kpis.sql` aus

Oder via SSH:

```bash
# In Render Shell
mysql -h <HOST> -u <USER> -p<PASSWORD> <DATABASE> < /path/to/add_contact_kpis.sql
```

## Alternativ: Manuell ausführen

```sql
ALTER TABLE contacts 
ADD COLUMN IF NOT EXISTS salutation VARCHAR(10) DEFAULT NULL COMMENT 'Sie or Du',
ADD COLUMN IF NOT EXISTS sentiment VARCHAR(20) DEFAULT NULL COMMENT 'positive, neutral, negative',
ADD COLUMN IF NOT EXISTS email_length_preference VARCHAR(20) DEFAULT NULL COMMENT 'short, medium, long',
ADD COLUMN IF NOT EXISTS avg_response_time_hours INT DEFAULT NULL COMMENT 'Average response time in hours',
ADD COLUMN IF NOT EXISTS communication_frequency VARCHAR(20) DEFAULT NULL COMMENT 'daily, weekly, monthly, rare',
ADD COLUMN IF NOT EXISTS last_sentiment_at DATETIME DEFAULT NULL COMMENT 'When sentiment was last analyzed',
ADD COLUMN IF NOT EXISTS kpis_updated_at DATETIME DEFAULT NULL COMMENT 'When KPIs were last calculated';

CREATE INDEX IF NOT EXISTS idx_contacts_salutation ON contacts(salutation);
CREATE INDEX IF NOT EXISTS idx_contacts_sentiment ON contacts(sentiment);
```

## Was wird hinzugefügt:

- ✅ `salutation` - Sie oder Du
- ✅ `sentiment` - positive, neutral, negative
- ✅ `email_length_preference` - short, medium, long
- ✅ `communication_frequency` - daily, weekly, monthly, rare
- ✅ `avg_response_time_hours` - Durchschnittliche Antwortzeit (noch nicht implementiert)
- ✅ `last_sentiment_at` - Timestamp des letzten Sentiment-Checks
- ✅ `kpis_updated_at` - Timestamp der letzten KPI-Berechnung

## Nach der Migration:

Die KPIs werden automatisch berechnet, wenn ein Kundenprofil generiert/aktualisiert wird.
