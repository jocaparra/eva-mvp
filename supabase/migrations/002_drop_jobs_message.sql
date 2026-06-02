-- Remove retenção de texto original de mensagens
ALTER TABLE jobs DROP COLUMN IF EXISTS message;
