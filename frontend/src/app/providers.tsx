"use client";

import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";

// Cargar Web3Provider solo cuando se necesita (lazy loading)
const Web3Provider = dynamic(
  () => import("@/providers/web3-provider").then((mod) => mod.Web3Provider),
  {
    ssr: false,
    loading: () => null,
  }
);

// Rutas que necesitan Web3
const WEB3_ROUTES = ["/blockchain", "/investments", "/dashboard"];

export function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const needsWeb3 = WEB3_ROUTES.some((route) => pathname?.startsWith(route));

  // Solo cargar Web3Provider en rutas que lo necesitan
  if (needsWeb3) {
    return <Web3Provider>{children}</Web3Provider>;
  }

  return <>{children}</>;
}
