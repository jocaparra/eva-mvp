import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { SidebarNav } from "./sidebar-nav";

export default async function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("status, role")
    .eq("id", user.id)
    .single();
  if (profile?.status !== "approved") redirect("/aguardando");

  return (
    <div className="flex min-h-screen bg-white">
      <aside className="flex w-52 shrink-0 flex-col border-r border-eva-border bg-eva-bg-alt">
        <div className="flex h-[60px] items-center border-b border-eva-border px-5">
          <Link href="/app" className="flex items-center">
            <Image
              src="/assets/logo-eva-black.png"
              alt="EVA"
              width={528}
              height={468}
              className="h-6 w-auto"
              priority
            />
          </Link>
        </div>
        <SidebarNav isAdmin={profile?.role === "admin"} />
      </aside>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
