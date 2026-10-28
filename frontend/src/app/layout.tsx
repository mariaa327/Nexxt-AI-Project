import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Navbar } from "@/components/Navbar";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Hackathon Starter",
  description:
    "Next.js, FastAPI and Supabase starter for building AI features quickly.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen antialiased">
        <div className="flex min-h-screen flex-col">
          <Navbar />
          <main className="flex-1">{children}</main>
          <footer className="border-t border-[var(--border)] px-4 py-6 text-sm text-[var(--muted)] sm:px-6">
            <div className="mx-auto flex max-w-5xl flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <span>AI Hackathon Starter — Next.js + FastAPI + Supabase</span>
              <span>Built for fast iteration, not production hardening.</span>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
