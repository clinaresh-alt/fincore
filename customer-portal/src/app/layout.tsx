import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SessionProvider } from "@/providers/session-provider";
import { QueryProvider } from "@/providers/query-provider";
import { ThemeProvider } from "@/providers/theme-provider";
import { NotificationsProvider } from "@/providers/notifications-provider";
import { Toaster } from "sonner";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-geist-sans",
});

export const metadata: Metadata = {
  title: {
    default: "FinCore - Remesas y Crypto",
    template: "%s | FinCore",
  },
  description:
    "Envía remesas internacionales de forma rápida y segura. Compra y vende criptomonedas con las mejores tasas.",
  keywords: [
    "remesas",
    "transferencias",
    "crypto",
    "USDC",
    "México",
    "fintech",
    "blockchain",
  ],
  authors: [{ name: "FinCore" }],
  creator: "FinCore",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL || "https://app.fincore.com"
  ),
  openGraph: {
    type: "website",
    locale: "es_MX",
    siteName: "FinCore",
    title: "FinCore - Remesas y Crypto",
    description:
      "Envía remesas internacionales de forma rápida y segura con tecnología blockchain.",
  },
  twitter: {
    card: "summary_large_image",
    title: "FinCore - Remesas y Crypto",
    description: "Remesas internacionales con tecnología blockchain.",
  },
  robots: {
    index: true,
    follow: true,
  },
  manifest: "/manifest.json",
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon-16x16.png",
    apple: "/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased`}>
        <SessionProvider>
          <ThemeProvider defaultTheme="system">
            <QueryProvider>
              <NotificationsProvider>
                {children}
              </NotificationsProvider>
              <Toaster
                position="top-center"
                expand={false}
                richColors
                closeButton
                toastOptions={{
                  duration: 4000,
                  classNames: {
                    toast: "!rounded-xl",
                  },
                }}
              />
            </QueryProvider>
          </ThemeProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
