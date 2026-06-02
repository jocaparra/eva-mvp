-- EVA MVP — execute no SQL Editor do Supabase

-- Jobs persistentes por cliente
CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone TEXT NOT NULL,
  company_name TEXT NOT NULL,
  document_type TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  ppt_path TEXT,
  ppt_filename TEXT,
  qa_passed BOOLEAN,
  qa_issues JSONB,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_phone ON jobs(phone);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- Assinaturas dos clientes
CREATE TABLE IF NOT EXISTS subscriptions (
  phone TEXT PRIMARY KEY,
  active BOOLEAN DEFAULT TRUE,
  jobs_this_month INTEGER DEFAULT 0,
  month TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone TEXT NOT NULL,
  action TEXT NOT NULL,
  resource_type TEXT,
  resource_id TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_phone ON audit_logs(phone);

-- Templates por cliente (metadados — arquivo no Storage)
CREATE TABLE IF NOT EXISTS client_templates (
  phone TEXT PRIMARY KEY,
  filename TEXT,
  storage_path TEXT,
  uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Políticas: cliente autenticado só vê seus dados (phone = auth.jwt()->>'phone')
-- O backend usa service_role e bypassa RLS.

CREATE POLICY IF NOT EXISTS jobs_phone_isolation ON jobs
  FOR ALL
  USING (phone = current_setting('request.jwt.claim.phone', true));

CREATE POLICY IF NOT EXISTS audit_logs_phone_isolation ON audit_logs
  FOR ALL
  USING (phone = current_setting('request.jwt.claim.phone', true));

-- Storage bucket privado para templates
INSERT INTO storage.buckets (id, name, public)
VALUES ('templates', 'templates', false)
ON CONFLICT (id) DO NOTHING;

-- Trigger updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS jobs_updated_at ON jobs;
CREATE TRIGGER jobs_updated_at
  BEFORE UPDATE ON jobs
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
