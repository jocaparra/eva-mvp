import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { WorkerEnv } from "./env";

/** Cliente Supabase do worker (service role — ignora RLS, só roda no servidor). */
export function createWorkerSupabase(env: WorkerEnv): SupabaseClient {
  return createClient(env.NEXT_PUBLIC_SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false },
  });
}
