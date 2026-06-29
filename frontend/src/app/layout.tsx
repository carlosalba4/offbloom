import type { Metadata, Viewport } from "next";
import { Fraunces, Manrope } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";

// Titulares: serif cálido y sereno.
const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  display: "swap",
});

// Cuerpo y UI: sans geométrico limpio.
const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "OffBloom — Sustituir, no prohibir",
  description:
    "Coach de bienestar digital que sustituye el scroll por alternativas offline contextualizadas. Privacy-first.",
};

export const viewport: Viewport = { themeColor: "#2A9D8F" };

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${fraunces.variable} ${manrope.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground font-sans">
        <SiteHeader />
        <div className="flex flex-1 flex-col">{children}</div>
      </body>
    </html>
  );
}
