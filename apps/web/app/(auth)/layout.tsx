import Image from "next/image";
import Link from "next/link";

export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="flex h-[60px] items-center border-b border-eva-border px-8">
        <Link href="/" className="flex items-center">
          <Image
            src="/assets/logo-eva-black.png"
            alt="EVA"
            width={528}
            height={468}
            className="h-[30px] w-auto"
            priority
          />
        </Link>
      </header>
      <main className="flex flex-1 items-center justify-center px-6 py-16">
        {children}
      </main>
    </div>
  );
}
