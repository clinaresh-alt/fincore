"use client";

import { SessionProvider as NextAuthSessionProvider, useSession } from "next-auth/react";
import { useEffect, useRef, type ReactNode } from "react";
import { setAuthToken } from "@/lib/api-client";

interface SessionProviderProps {
  children: ReactNode;
}

/**
 * Componente interno que sincroniza el token de sesión con el apiClient
 */
function AuthTokenSync({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const tokenSetRef = useRef(false);

  useEffect(() => {
    // Limpiar flag de logout al cargar la app (evitar ciclos por estado anterior)
    if (typeof window !== "undefined") {
      // Solo limpiar si no estamos en proceso de logout activo
      const currentPath = window.location.pathname;
      if (!currentPath.startsWith("/api/auth")) {
        sessionStorage.removeItem("logout_in_progress");
      }
    }
  }, []);

  useEffect(() => {
    if (status === "authenticated" && session?.accessToken) {
      // Solo configurar el token si no lo hemos hecho ya o si cambió
      if (!tokenSetRef.current) {
        console.log("[SessionProvider] Configurando token de autenticación");
        setAuthToken(session.accessToken);
        tokenSetRef.current = true;
      }
    } else if (status === "unauthenticated") {
      console.log("[SessionProvider] Usuario no autenticado, limpiando token");
      setAuthToken(null);
      tokenSetRef.current = false;
    }
  }, [session, status]);

  return <>{children}</>;
}

export function SessionProvider({ children }: SessionProviderProps) {
  return (
    <NextAuthSessionProvider
      // Refetch session cada 5 minutos
      refetchInterval={5 * 60}
      // Refetch al volver a la pestaña
      refetchOnWindowFocus={true}
    >
      <AuthTokenSync>{children}</AuthTokenSync>
    </NextAuthSessionProvider>
  );
}
