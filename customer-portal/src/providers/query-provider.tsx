"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState, type ReactNode } from "react";

interface QueryProviderProps {
  children: ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Tiempo que los datos se consideran frescos
            staleTime: 1000 * 60 * 5, // 5 minutos
            // Tiempo que los datos permanecen en cache
            gcTime: 1000 * 60 * 30, // 30 minutos (antes cacheTime)
            // Reintentos en caso de error
            retry: (failureCount, error) => {
              // No reintentar en errores 4xx
              if (error instanceof Error && error.message.includes("4")) {
                return false;
              }
              return failureCount < 2;
            },
            // Refetch en window focus
            refetchOnWindowFocus: true,
            // Refetch en reconexión
            refetchOnReconnect: true,
          },
          mutations: {
            // Reintentos para mutaciones
            retry: 1,
            // Callback global de error
            onError: (error) => {
              console.error("Mutation error:", error);
            },
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} position="bottom" />
      )}
    </QueryClientProvider>
  );
}
