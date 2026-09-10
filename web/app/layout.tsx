import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const siteUrl = process.env.SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "WhyDidThisFail?",
  description:
    "Paste a build, test, or deploy failure and get the real cause, an explanation, and exact commands to fix it.",
  openGraph: {
    siteName: "WhyDidThisFail?",
    type: "website",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <header className="border-b border-border">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
            <Link href="/" className="text-sm font-bold tracking-tight">
              WhyDidThisFail?
            </Link>
          </div>
        </header>
        <div className="flex flex-1 flex-col">{children}</div>
        <footer className="border-t border-border py-6">
          <div className="mx-auto max-w-5xl px-4 text-xs text-muted">
            Logs are sanitized before storage. See how on any result page.
          </div>
        </footer>
      </body>
    </html>
  );
}
