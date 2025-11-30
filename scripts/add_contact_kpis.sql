-- Add KPI fields to contacts table
-- Run this on your production database

ALTER TABLE contacts 
ADD COLUMN IF NOT EXISTS salutation VARCHAR(10) DEFAULT NULL COMMENT 'Sie or Du',
ADD COLUMN IF NOT EXISTS sentiment VARCHAR(20) DEFAULT NULL COMMENT 'positive, neutral, negative',
ADD COLUMN IF NOT EXISTS email_length_preference VARCHAR(20) DEFAULT NULL COMMENT 'short, medium, long',
ADD COLUMN IF NOT EXISTS avg_response_time_hours INT DEFAULT NULL COMMENT 'Average response time in hours',
ADD COLUMN IF NOT EXISTS communication_frequency VARCHAR(20) DEFAULT NULL COMMENT 'daily, weekly, monthly, rare',
ADD COLUMN IF NOT EXISTS last_sentiment_at DATETIME DEFAULT NULL COMMENT 'When sentiment was last analyzed',
ADD COLUMN IF NOT EXISTS kpis_updated_at DATETIME DEFAULT NULL COMMENT 'When KPIs were last calculated';

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_contacts_salutation ON contacts(salutation);
CREATE INDEX IF NOT EXISTS idx_contacts_sentiment ON contacts(sentiment);
