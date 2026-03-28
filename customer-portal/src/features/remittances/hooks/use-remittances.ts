import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type {
  Remittance,
  RemittanceQuote,
  QuoteRequest,
  CreateRemittanceRequest,
  RemittanceLimits,
  PaginatedResponse,
} from "@/types";

// Query Keys
export const remittanceKeys = {
  all: ["remittances"] as const,
  lists: () => [...remittanceKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) =>
    [...remittanceKeys.lists(), filters] as const,
  details: () => [...remittanceKeys.all, "detail"] as const,
  detail: (id: string) => [...remittanceKeys.details(), id] as const,
  quote: (params: QuoteRequest) => [...remittanceKeys.all, "quote", params] as const,
  limits: () => [...remittanceKeys.all, "limits"] as const,
};

// Hooks

/**
 * Hook para obtener lista de remesas del usuario
 */
export function useRemittances(params?: {
  page?: number;
  pageSize?: number;
  status?: string;
}) {
  const { page = 1, pageSize = 10, status } = params ?? {};

  return useQuery({
    queryKey: remittanceKeys.list({ page, pageSize, status }),
    queryFn: () =>
      apiClient.get<PaginatedResponse<Remittance>>("/remittances", {
        page,
        page_size: pageSize,
        status,
      }),
  });
}

/**
 * Hook para obtener una remesa por ID
 */
export function useRemittance(id: string) {
  return useQuery({
    queryKey: remittanceKeys.detail(id),
    queryFn: () => apiClient.get<Remittance>(`/remittances/${id}`),
    enabled: !!id,
  });
}

/**
 * Hook para obtener cotización de remesa
 */
export function useRemittanceQuote(params: QuoteRequest | null) {
  return useQuery({
    queryKey: params ? remittanceKeys.quote(params) : ["disabled"],
    queryFn: () => apiClient.post<RemittanceQuote>("/remittances/quote", params),
    enabled: !!params && params.amount_source > 0,
    staleTime: 1000 * 60, // 1 minuto
    gcTime: 1000 * 60 * 5, // 5 minutos
  });
}

/**
 * Hook para obtener límites de remesa del usuario
 */
export function useRemittanceLimits() {
  return useQuery({
    queryKey: remittanceKeys.limits(),
    queryFn: () => apiClient.get<RemittanceLimits>("/remittances/limits"),
    staleTime: 1000 * 60 * 5, // 5 minutos
  });
}

/**
 * Hook para crear una remesa
 */
export function useCreateRemittance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateRemittanceRequest) =>
      apiClient.post<Remittance>("/remittances", data),
    onSuccess: () => {
      // Invalidar lista de remesas
      queryClient.invalidateQueries({ queryKey: remittanceKeys.lists() });
      // Invalidar límites (pueden haber cambiado)
      queryClient.invalidateQueries({ queryKey: remittanceKeys.limits() });
    },
  });
}

/**
 * Hook para crear remesa con firma de transacción
 */
export function useCreateRemittanceWithSignature() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      data,
      signature,
    }: {
      data: CreateRemittanceRequest;
      signature: string;
    }) => apiClient.postWithSignature<Remittance>("/remittances", data, signature),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: remittanceKeys.lists() });
      queryClient.invalidateQueries({ queryKey: remittanceKeys.limits() });
    },
  });
}

/**
 * Hook para bloquear fondos en escrow
 */
export function useLockFunds() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      remittanceId,
      walletAddress,
    }: {
      remittanceId: string;
      walletAddress: string;
    }) =>
      apiClient.post<{ tx_hash: string; status: string }>(
        `/remittances/${remittanceId}/lock`,
        { wallet_address: walletAddress }
      ),
    onSuccess: (_, { remittanceId }) => {
      queryClient.invalidateQueries({
        queryKey: remittanceKeys.detail(remittanceId),
      });
      queryClient.invalidateQueries({ queryKey: remittanceKeys.lists() });
    },
  });
}

/**
 * Hook para cancelar una remesa
 */
export function useCancelRemittance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (remittanceId: string) =>
      apiClient.post<{ success: boolean }>(`/remittances/${remittanceId}/cancel`),
    onSuccess: (_, remittanceId) => {
      queryClient.invalidateQueries({
        queryKey: remittanceKeys.detail(remittanceId),
      });
      queryClient.invalidateQueries({ queryKey: remittanceKeys.lists() });
    },
  });
}
