import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Design Factory Control Center",
  description: "Human Control Center for the autonomous Etsy wall-art design factory.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-canvas text-neutral-100">
        <div className="flex min-h-screen flex-col">
          <header className="border-b border-border bg-panel">
            <nav className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4">
              <span className="text-sm font-semibold tracking-wide text-accent">DESIGN FACTORY</span>
              <Link href="/" className="text-sm text-neutral-300 hover:text-white">
                Dashboard
              </Link>
              <Link href="/candidates" className="text-sm text-neutral-300 hover:text-white">
                Approval Queue
              </Link>
              <Link href="/market-signals" className="text-sm text-neutral-300 hover:text-white">
                Market Signals
              </Link>
              <Link href="/getvela" className="text-sm text-neutral-300 hover:text-white">
                Getvela Export
              </Link>
            </nav>
          </header>
          <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
