"use client";

import { RainbowKitProvider, darkTheme, lightTheme } from "@rainbow-me/rainbowkit";
import { WagmiProvider } from "wagmi";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { config } from "@/lib/wagmi";

import "@rainbow-me/rainbowkit/styles.css";

// Cliente de React Query para wagmi
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutos
      refetchOnWindowFocus: false,
    },
  },
});

// Tema personalizado para RainbowKit (FinCore branding)
const fincoreTheme = darkTheme({
  accentColor: "#3b82f6", // Blue-500 (color primario de FinCore)
  accentColorForeground: "white",
  borderRadius: "medium",
  fontStack: "system",
  overlayBlur: "small",
});

interface Web3ProviderProps {
  children: React.ReactNode;
}

export function Web3Provider({ children }: Web3ProviderProps) {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider
          theme={fincoreTheme}
          locale="es-419"
          modalSize="compact"
          appInfo={{
            appName: "FinCore",
            disclaimer: ({ Text, Link }) => (
              <Text>
                Al conectar tu wallet, aceptas los{" "}
                <Link href="/terms">Terminos de Servicio</Link> y{" "}
                <Link href="/privacy">Politica de Privacidad</Link> de FinCore.
              </Text>
            ),
          }}
        >
          {children}
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}
