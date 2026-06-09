import type { SupabaseClient } from "@supabase/supabase-js";
import type { DeliverableTipo } from "@eva/shared";
import { generateDeliverable } from "./documents";

const BUCKET = "deliverables";

/**
 * Gera o documento final, sobe no Storage (bucket privado) e registra na
 * tabela deliverables. Retorna o nome do arquivo entregue.
 */
export async function deliverDocument(params: {
  supabase: SupabaseClient;
  jobId: string;
  userId: string;
  title: string;
  tipo: DeliverableTipo;
  content: string;
}): Promise<string> {
  const { supabase, jobId, userId, title, tipo, content } = params;

  const documento = await generateDeliverable({ tipo, title, content });
  const storagePath = `${userId}/${jobId}/${documento.filename}`;

  const { error: uploadError } = await supabase.storage
    .from(BUCKET)
    .upload(storagePath, documento.buffer, {
      contentType: documento.contentType,
      upsert: true,
    });
  if (uploadError) {
    throw new Error(`Erro ao subir o documento no Storage: ${uploadError.message}`);
  }

  const { error: insertError } = await supabase.from("deliverables").insert({
    job_id: jobId,
    tipo,
    filename: documento.filename,
    storage_path: storagePath,
    size_bytes: documento.buffer.byteLength,
  });
  if (insertError) {
    throw new Error(`Erro ao registrar o entregável: ${insertError.message}`);
  }

  return documento.filename;
}
