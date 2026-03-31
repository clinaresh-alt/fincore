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
      apiClient.post<{ message: string }>("/security/password/change", data),
  });
}

// ============ Dispositivos ============

export interface Device {
  id: string;
  device_name: string | null;
  browser_name: string | null;
  os_name: string | null;
  device_type: string | null;
  last_ip: string | null;
  last_country: string | null;
  last_city: string | null;
  status: "trusted" | "unknown" | "suspicious" | "blocked";
  is_current: boolean;
  risk_score: number;
  is_vpn: boolean;
  is_tor: boolean;
  first_seen_at: string;
  last_seen_at: string;
}

export interface DeviceListResponse {
  devices: Device[];
  total: number;
}

export const deviceKeys = {
  all: ["devices"] as const,
  list: () => [...deviceKeys.all, "list"] as const,
};

export function useDevices() {
  return useQuery({
    queryKey: deviceKeys.list(),
    queryFn: () => apiClient.get<DeviceListResponse>("/security/devices"),
  });
}

export function useUpdateDevice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      deviceId,
      data,
    }: {
      deviceId: string;
      data: { device_name?: string; status?: "trusted" | "blocked" };
    }) => apiClient.put<{ message: string }>(`/security/devices/${deviceId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: deviceKeys.all });
    },
  });
}

export function useDeleteDevice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (deviceId: string) =>
      apiClient.delete<{ message: string }>(`/security/devices/${deviceId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: deviceKeys.all });
    },
  });
}

// ============ Sesiones ============

export interface Session {
  id: string;
  device_id: string | null;
  device_name: string | null;
  ip_address: string | null;
  country: string | null;
  city: string | null;
  is_current: boolean;
  created_at: string;
  last_activity_at: string;
  expires_at: string;
}

export interface SessionListResponse {
  sessions: Session[];
  total: number;
}

export const sessionKeys = {
  all: ["sessions"] as const,
  list: () => [...sessionKeys.all, "list"] as const,
};

export function useSessions() {
  return useQuery({
    queryKey: sessionKeys.list(),
    queryFn: () => apiClient.get<SessionListResponse>("/security/sessions"),
  });
}

export function useRevokeSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { session_id?: string; revoke_all?: boolean }) =>
      apiClient.post<{ message: string }>("/security/sessions/revoke", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionKeys.all });
    },
  });
}

// ============ Actividad de Seguridad ============

export interface SecurityActivity {
  id: string;
  action: string;
  description: string;
  ip_address: string | null;
  device_info: string | null;
  country: string | null;
  timestamp: string;
  is_suspicious: boolean;
}

export interface SecurityActivityListResponse {
  activities: SecurityActivity[];
  total: number;
}

export function useSecurityActivity(limit: number = 50) {
  return useQuery({
    queryKey: [...securityKeys.all, "activity", limit],
    queryFn: () =>
      apiClient.get<SecurityActivityListResponse>(`/security/activity?limit=${limit}`),
  });
}

// ============ Resumen de Seguridad ============

export interface SecuritySummary {
  mfa_enabled: boolean;
  mfa_backup_codes_remaining: number;
  anti_phishing_configured: boolean;
  total_devices: number;
  trusted_devices: number;
  active_sessions: number;
  whitelisted_addresses: number;
  addresses_in_quarantine: number;
  is_frozen: boolean;
  password_last_changed: string | null;
  password_expires_at: string | null;
  security_score: number;
  recommendations: string[];
}

export function useSecuritySummary() {
  return useQuery({
    queryKey: [...securityKeys.all, "summary"],
    queryFn: () => apiClient.get<SecuritySummary>("/security/summary"),
  });
}

// ============ Congelamiento de Cuenta ============

export function useFreezeAccount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { reason?: string }) =>
      apiClient.post<{ is_frozen: boolean; frozen_at: string }>("/security/freeze", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: securityKeys.all });
    },
  });
}

export function useFreezeStatus() {
  return useQuery({
    queryKey: [...securityKeys.all, "freeze-status"],
    queryFn: () =>
      apiClient.get<{ is_frozen: boolean; frozen_at: string | null }>("/security/freeze/status"),
  });
}

// ============ Anti-Phishing ============

export interface AntiPhishingResponse {
  is_configured: boolean;
  phrase_hint: string | null;
  created_at: string | null;
}

export function useAntiPhishing() {
  return useQuery({
    queryKey: [...securityKeys.all, "anti-phishing"],
    queryFn: () => apiClient.get<AntiPhishingResponse>("/security/anti-phishing"),
  });
}

export function useSetupAntiPhishing() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { phrase: string; phrase_hint?: string }) =>
      apiClient.post<AntiPhishingResponse>("/security/anti-phishing", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: securityKeys.all });
    },
  });
}

// ============ Backup Codes MFA ============

export interface BackupCodesResponse {
  codes: string[];
  warning: string;
  generated_at: string;
}

export interface BackupCodesStatus {
  total_codes: number;
  used_codes: number;
  remaining_codes: number;
  last_used_at: string | null;
}

export function useBackupCodesStatus() {
  return useQuery({
    queryKey: [...securityKeys.all, "backup-codes-status"],
    queryFn: () => apiClient.get<BackupCodesStatus>("/security/mfa/backup-codes/status"),
  });
}

export function useGenerateBackupCodes() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => apiClient.post<BackupCodesResponse>("/security/mfa/backup-codes", {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: securityKeys.all });
    },
  });
}

// ============ Whitelist de Retiro ============

export interface WithdrawalWhitelistAddress {
  id: string;
  address: string;
  label: string | null;
  network: string;
  status: "pending" | "active" | "suspended" | "cancelled";
  is_in_quarantine: boolean;
  quarantine_ends_at: string | null;
  created_at: string;
  activated_at: string | null;
}

export interface WhitelistListResponse {
  addresses: WithdrawalWhitelistAddress[];
  total: number;
  pending_count: number;
}

export const whitelistKeys = {
  all: ["whitelist"] as const,
  list: () => [...whitelistKeys.all, "list"] as const,
};

export function useWhitelistAddresses() {
  return useQuery({
    queryKey: whitelistKeys.list(),
    queryFn: () => apiClient.get<WhitelistListResponse>("/security/whitelist"),
  });
}

export function useAddWhitelistAddress() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { address: string; network: string; label?: string }) =>
      apiClient.post<WithdrawalWhitelistAddress>("/security/whitelist", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: whitelistKeys.all });
      queryClient.invalidateQueries({ queryKey: securityKeys.all });
    },
  });
}

export function useDeleteWhitelistAddress() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (addressId: string) =>
      apiClient.delete<{ message: string }>(`/security/whitelist/${addressId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: whitelistKeys.all });
      queryClient.invalidateQueries({ queryKey: securityKeys.all });
    },
  });
}
