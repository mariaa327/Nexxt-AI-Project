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
  title: "Overdraft Guard",
  description:
    "An agent that anticipates your bills and finds the cheapest way to avoid an overdraft.",
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
              <span>Overdraft Guard — hackathon demo with simulated data</span>
              <span>Transfers are simulated; no real bank is contacted.</span>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
