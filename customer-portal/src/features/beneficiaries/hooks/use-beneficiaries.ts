"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import type { Beneficiary, RecipientInfo } from "@/types";

const STORAGE_KEY = "fincore_beneficiaries";

// Keys para React Query
export const beneficiaryKeys = {
  all: ["beneficiaries"] as const,
  lists: () => [...beneficiaryKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) => [...beneficiaryKeys.lists(), filters] as const,
  details: () => [...beneficiaryKeys.all, "detail"] as const,
  detail: (id: string) => [...beneficiaryKeys.details(), id] as const,
};

// Helper para obtener beneficiarios de localStorage
function getBeneficiariesFromStorage(userId: string): Beneficiary[] {
  if (typeof window === "undefined") return [];

  try {
    const data = localStorage.getItem(`${STORAGE_KEY}_${userId}`);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

// Helper para guardar beneficiarios en localStorage
function saveBeneficiariesToStorage(userId: string, beneficiaries: Beneficiary[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(`${STORAGE_KEY}_${userId}`, JSON.stringify(beneficiaries));
}

// Input para crear beneficiario
export interface CreateBeneficiaryInput {
  nickname: string;
  recipient_info: RecipientInfo;
  is_favorite?: boolean;
}

// Input para actualizar beneficiario
export interface UpdateBeneficiaryInput {
  id: string;
  nickname?: string;
  recipient_info?: Partial<RecipientInfo>;
  is_favorite?: boolean;
}

// Hook para obtener lista de beneficiarios
export function useBeneficiaries(options?: { favorites_only?: boolean }) {
  const { data: session } = useSession();
  const userId = session?.user?.email || "anonymous";

  return useQuery({
    queryKey: beneficiaryKeys.list(options || {}),
    queryFn: async () => {
      let beneficiaries = getBeneficiariesFromStorage(userId);

      if (options?.favorites_only) {
        beneficiaries = beneficiaries.filter((b) => b.is_favorite);
      }

      // Ordenar: favoritos primero, luego por último uso
      return beneficiaries.sort((a, b) => {
        if (a.is_favorite !== b.is_favorite) {
          return a.is_favorite ? -1 : 1;
        }
        const dateA = a.last_used_at ? new Date(a.last_used_at).getTime() : 0;
        const dateB = b.last_used_at ? new Date(b.last_used_at).getTime() : 0;
        return dateB - dateA;
      });
    },
    enabled: !!session,
    staleTime: Infinity, // Los datos locales no cambian externamente
  });
}

// Hook para obtener un beneficiario específico
export function useBeneficiary(id: string) {
  const { data: session } = useSession();
  const userId = session?.user?.email || "anonymous";

  return useQuery({
    queryKey: beneficiaryKeys.detail(id),
    queryFn: async () => {
      const beneficiaries = getBeneficiariesFromStorage(userId);
      const beneficiary = beneficiaries.find((b) => b.id === id);
      if (!beneficiary) {
        throw new Error("Beneficiario no encontrado");
      }
      return beneficiary;
    },
    enabled: !!session && !!id,
  });
}

// Hook para crear beneficiario
export function useCreateBeneficiary() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();
  const userId = session?.user?.email || "anonymous";

  return useMutation({
    mutationFn: async (input: CreateBeneficiaryInput) => {
      const beneficiaries = getBeneficiariesFromStorage(userId);

      // Verificar duplicados por CLABE o cuenta
      const isDuplicate = beneficiaries.some((b) => {
        if (input.recipient_info.clabe && b.recipient_info.clabe === input.recipient_info.clabe) {
          return true;
        }
        if (
          input.recipient_info.account_number &&
          b.recipient_info.account_number === input.recipient_info.account_number &&
          b.recipient_info.bank_name === input.recipient_info.bank_name
        ) {
          return true;
        }
        return false;
      });

      if (isDuplicate) {
        throw new Error("Ya existe un beneficiario con estos datos bancarios");
      }

      const newBeneficiary: Beneficiary = {
        id: crypto.randomUUID(),
        user_id: userId,
        nickname: input.nickname,
        recipient_info: input.recipient_info,
        is_favorite: input.is_favorite || false,
        created_at: new Date().toISOString(),
      };

      beneficiaries.push(newBeneficiary);
      saveBeneficiariesToStorage(userId, beneficiaries);

      return newBeneficiary;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: beneficiaryKeys.all });
    },
  });
}

// Hook para actualizar beneficiario
export function useUpdateBeneficiary() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();
  const userId = session?.user?.email || "anonymous";

  return useMutation({
    mutationFn: async (input: UpdateBeneficiaryInput) => {
      const beneficiaries = getBeneficiariesFromStorage(userId);
      const index = beneficiaries.findIndex((b) => b.id === input.id);

      if (index === -1) {
        throw new Error("Beneficiario no encontrado");
      }

      const updated: Beneficiary = {
        ...beneficiaries[index],
        nickname: input.nickname ?? beneficiaries[index].nickname,
        recipient_info: {
          ...beneficiaries[index].recipient_info,
          ...input.recipient_info,
        },
        is_favorite: input.is_favorite ?? beneficiaries[index].is_favorite,
      };

      beneficiaries[index] = updated;
      saveBeneficiariesToStorage(userId, beneficiaries);

      return updated;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: beneficiaryKeys.all });
      queryClient.setQueryData(beneficiaryKeys.detail(data.id), data);
    },
  });
}

// Hook para eliminar beneficiario
export function useDeleteBeneficiary() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();
  const userId = session?.user?.email || "anonymous";

  return useMutation({
    mutationFn: async (id: string) => {
      const beneficiaries = getBeneficiariesFromStorage(userId);
      const filtered = beneficiaries.filter((b) => b.id !== id);

      if (filtered.length === beneficiaries.length) {
        throw new Error("Beneficiario no encontrado");
      }

      saveBeneficiariesToStorage(userId, filtered);
      return id;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: beneficiaryKeys.all });
    },
  });
}

// Hook para marcar como favorito
export function useToggleFavorite() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();
  const userId = session?.user?.email || "anonymous";

  return useMutation({
    mutationFn: async (id: string) => {
      const beneficiaries = getBeneficiariesFromStorage(userId);
      const index = beneficiaries.findIndex((b) => b.id === id);

      if (index === -1) {
        throw new Error("Beneficiario no encontrado");
      }

      beneficiaries[index].is_favorite = !beneficiaries[index].is_favorite;
      saveBeneficiariesToStorage(userId, beneficiaries);

      return beneficiaries[index];
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: beneficiaryKeys.all });
      queryClient.setQueryData(beneficiaryKeys.detail(data.id), data);
    },
  });
}

// Hook para marcar último uso (cuando se usa en una remesa)
export function useMarkBeneficiaryUsed() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();
  const userId = session?.user?.email || "anonymous";

  return useMutation({
    mutationFn: async (id: string) => {
      const beneficiaries = getBeneficiariesFromStorage(userId);
      const index = beneficiaries.findIndex((b) => b.id === id);

      if (index !== -1) {
        beneficiaries[index].last_used_at = new Date().toISOString();
        saveBeneficiariesToStorage(userId, beneficiaries);
      }

      return beneficiaries[index];
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: beneficiaryKeys.all });
    },
  });
}
