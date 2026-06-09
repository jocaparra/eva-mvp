-- Bucket privado para upload temporário de documentos (web)
INSERT INTO storage.buckets (id, name, public)
VALUES ('client-documents', 'client-documents', false)
ON CONFLICT (id) DO NOTHING;

-- Políticas: usuário autenticado só acessa pasta com seu phone
-- Backend usa service_role e bypassa RLS para upload/delete efêmero.

CREATE POLICY IF NOT EXISTS client_documents_select_own ON storage.objects
  FOR SELECT
  USING (
    bucket_id = 'client-documents'
    AND (storage.foldername(name))[1] = auth.jwt() ->> 'phone'
  );

CREATE POLICY IF NOT EXISTS client_documents_insert_own ON storage.objects
  FOR INSERT
  WITH CHECK (
    bucket_id = 'client-documents'
    AND (storage.foldername(name))[1] = auth.jwt() ->> 'phone'
  );

CREATE POLICY IF NOT EXISTS client_documents_delete_own ON storage.objects
  FOR DELETE
  USING (
    bucket_id = 'client-documents'
    AND (storage.foldername(name))[1] = auth.jwt() ->> 'phone'
  );

CREATE POLICY IF NOT EXISTS client_documents_update_own ON storage.objects
  FOR UPDATE
  USING (
    bucket_id = 'client-documents'
    AND (storage.foldername(name))[1] = auth.jwt() ->> 'phone'
  );
