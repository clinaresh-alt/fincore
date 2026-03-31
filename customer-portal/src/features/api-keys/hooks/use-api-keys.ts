"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// ==================== TYPES ====================

export interface APIKey {
  id: string;
  name: string;
  description?: string;
  key_prefix: string;
  permissions: string[];
  allowed_ips?: string[];
  status: "active" | "revoked" | "expired";
  expires_at?: string;
  rate_limit_per_minute: number;
  rate_limit_per_day: number;
  last_used_at?: string;
  last_used_ip?: string;
  total_requests: number;
  created_at: string;
}

export interface APIKeyCreated {
  id: string;
  name: string;
  key: string; // Solo se muestra una vez
  key_prefix: string;
  permissions: string[];
  expires_at?: string;
  created_at: string;
  warning: string;
}

export interface APIKeyCreateInput {
  name: string;
  description?: string;
  permissions: string[];
  allowed_ips?: string[];
  expires_at?: string;
  rate_limit_per_minute?: number;
  rate_limit_per_day?: number;
}

export interface APIKeyUpdateInput {
  name?: string;
  description?: string;
  permissions?: string[];
  allowed_ips?: string[];
  rate_limit_per_minute?: number;
  rate_limit_per_day?: number;
}

export interface APIKeyLog {
  id: string;
  endpoint: string;
  method: string;
  ip_address?: string;
  status_code?: number;
  response_time_ms?: number;
  error_message?: string;
  created_at: string;
}

export interface APIKeyLogsResponse {
  logs: APIKeyLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface APIKeyStats {
  api_key_id: string;
  total_requests: number;
  requests_today: number;
  requests_this_month: number;
  avg_response_time_ms: number;
  error_rate: number;
  top_endpoints: { endpoint: string; count: number }[];
  requests_by_day: { date: string; count: number }[];
}

export interface Permission {
  code: string;
  name: string;
  category: string;
}

// ==================== QUERY KEYS ====================

export const apiKeysKeys = {
  all: ["api-keys"] as const,
  list: () => [...apiKeysKeys.all, "list"] as const,
  detail: (id: string) => [...apiKeysKeys.all, "detail", id] as const,
  logs: (id: string, page?: number) =>
    [...apiKeysKeys.all, "logs", id, page] as const,
  stats: (id: string) => [...apiKeysKeys.all, "stats", id] as const,
  permissions: () => [...apiKeysKeys.all, "permissions"] as const,
};

// ==================== HOOKS ====================

export function useAPIKeys() {
  return useQuery({
    queryKey: apiKeysKeys.list(),
    queryFn: () => apiClient.get<APIKey[]>("/api-keys"),
  });
}

export function useAPIKey(id: string) {
  return useQuery({
    queryKey: apiKeysKeys.detail(id),
    queryFn: () => apiClient.get<APIKey>(`/api-keys/${id}`),
    enabled: !!id,
  });
}

export function useCreateAPIKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: APIKeyCreateInput) =>
      apiClient.post<APIKeyCreated>("/api-keys", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiKeysKeys.list() });
    },
  });
}

export function useUpdateAPIKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: APIKeyUpdateInput }) =>
      apiClient.put<APIKey>(`/api-keys/${id}`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: apiKeysKeys.list() });
      queryClient.invalidateQueries({
        queryKey: apiKeysKeys.detail(variables.id),
      });
    },
  });
}

export function useRevokeAPIKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete<{ message: string; key_id: string }>(`/api-keys/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiKeysKeys.list() });
    },
  });
}

export function useAPIKeyLogs(id: string, page: number = 1, pageSize: number = 50) {
  return useQuery({
    queryKey: apiKeysKeys.logs(id, page),
    queryFn: () =>
      apiClient.get<APIKeyLogsResponse>(
        `/api-keys/${id}/logs?limit=${pageSize}&offset=${(page - 1) * pageSize}`
      ),
    enabled: !!id,
  });
}

export function useAPIKeyStats(id: string) {
  return useQuery({
    queryKey: apiKeysKeys.stats(id),
    queryFn: () => apiClient.get<APIKeyStats>(`/api-keys/${id}/stats`),
    enabled: !!id,
  });
}

export function useAvailablePermissions() {
  return useQuery({
    queryKey: apiKeysKeys.permissions(),
    queryFn: () =>
      apiClient.get<{ permissions: Permission[] }>("/api-keys/permissions/available"),
    staleTime: 1000 * 60 * 60, // 1 hora
  });
}
