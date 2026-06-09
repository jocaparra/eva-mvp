"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

const LINKS = [
  { href: "/app", label: "Novo job", exact: true },
  { href: "/app/jobs", label: "Jobs", exact: false },
];

export function SidebarNav({ isAdmin }: { isAdmin: boolean }) {
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  function isActive(href: string, exact: boolean): boolean {
    return exact ? pathname === href : pathname.startsWith(href);
  }

  return (
    <nav className="flex flex-1 flex-col p-3">
      <div className="flex flex-col gap-1">
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`rounded-eva px-3 py-2 text-sm transition-colors ${
              isActive(link.href, link.exact)
                ? "bg-white font-medium text-eva-text shadow-sm"
                : "text-eva-secondary hover:bg-white hover:text-eva-text"
            }`}
          >
            {link.label}
          </Link>
        ))}
        {isAdmin ? (
          <Link
            href="/admin"
            className="rounded-eva px-3 py-2 text-sm text-eva-secondary transition-colors hover:bg-white hover:text-eva-text"
          >
            Admin
          </Link>
        ) : null}
      </div>
      <div className="mt-auto">
        <button
          type="button"
          onClick={handleSignOut}
          className="w-full rounded-eva px-3 py-2 text-left text-sm text-eva-secondary transition-colors hover:bg-white hover:text-eva-text"
        >
          Sair
        </button>
      </div>
    </nav>
  );
}
