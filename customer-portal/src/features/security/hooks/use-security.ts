"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// Types
export interface MFASetupResponse {
  secret: string;
  qr_code_base64: string;
  manual_entry_key: string;
}

export interface UserSecurityInfo {
  id: string;
  email: string;
  mfa_enabled: boolean;
  ultimo_login: string | null;
  created_at: string;
}

export interface AuditLogEntry {
  id: string;
  action: string;
  ip_address: string | null;
  user_agent: string | null;
  description: string | null;
  created_at: string;
}

// Query keys
export const securityKeys = {
  all: ["security"] as const,
  me: () => [...securityKeys.all, "me"] as const,
  auditLog: (filters?: Record<string, unknown>) => [...securityKeys.all, "audit", filters] as const,
};

// Hooks

// Obtener info del usuario actual
export function useCurrentUser() {
  return useQuery({
    queryKey: securityKeys.me(),
    queryFn: () => apiClient.get<UserSecurityInfo>("/auth/me"),
  });
}

// Configurar MFA (genera QR)
export function useSetupMFA() {
  return useMutation({
    mutationFn: () => apiClient.post<MFASetupResponse>("/auth/mfa/setup", {}),
  });
}

// Habilitar MFA (verificar primer código)
export function useEnableMFA() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (code: string) =>
      apiClient.post<{ message: string }>(`/auth/mfa/enable?code=${code}`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: securityKeys.me() });
    },
  });
}

// Deshabilitar MFA (necesita endpoint adicional en backend)
export function useDisableMFA() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (code: string) =>
      apiClient.post<{ message: string }>(`/auth/mfa/disable?code=${code}`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: securityKeys.me() });
    },
  });
}

// Cambiar contraseña
export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { current_password: string; new_password: string }) =>
      apiClient.post<{ message: string }>("/auth/change-password", data),
  });
}
