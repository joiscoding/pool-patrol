import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Pool Patrol",
  description: "Vanpool misuse detection system",
};

function TeslaLogo({ className }: { className?: string }) {
  return (
    <img
      src="/tesla-logo.png"
      alt="Tesla"
      className={className}
    />
  );
}

function Navigation() {
  return (
    <header className="border-b border-neutral-200">
      <nav className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-3">
          <TeslaLogo className="h-6 w-auto" />
          <span className="text-base font-semibold tracking-tight">Pool Patrol</span>
        </Link>
        <div className="flex items-center gap-6">
          <Link
            href="/dev/create"
            className="text-sm text-neutral-500 hover:text-neutral-900 transition-colors"
          >
            + New Vanpool
          </Link>
          <a 
            href="https://joyax.co" 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors"
          >
            Product of Joyax
          </a>
        </div>
      </nav>
    </header>
  );
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased bg-white`}>
        <Navigation />
        <main>{children}</main>
      </body>
    </html>
  );
}
