import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import AppShell from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: "LogisPLAN - Gestion Logistica",
  description: "Dashboard de gestion de flota - Severino Logistica",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
