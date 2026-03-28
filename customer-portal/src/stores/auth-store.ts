import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  mfaPending: boolean;
  mfaPendingToken: string | null;

  // Acciones
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setMfaPending: (pending: boolean, token?: string) => void;
  logout: () => void;
  updateUser: (updates: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      mfaPending: false,
      mfaPendingToken: null,

      setUser: (user) =>
        set({
          user,
          isAuthenticated: !!user,
          isLoading: false,
          mfaPending: false,
          mfaPendingToken: null,
        }),

      setLoading: (isLoading) => set({ isLoading }),

      setMfaPending: (mfaPending, mfaPendingToken) =>
        set({ mfaPending, mfaPendingToken: mfaPendingToken ?? null }),

      logout: () =>
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          mfaPending: false,
          mfaPendingToken: null,
        }),

      updateUser: (updates) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...updates } : null,
        })),
    }),
    {
      name: "fincore-auth",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        // Solo persistir datos no sensibles
        user: state.user
          ? {
              id: state.user.id,
              email: state.user.email,
              first_name: state.user.first_name,
              last_name: state.user.last_name,
              role: state.user.role,
              kyc_status: state.user.kyc_status,
              kyc_level: state.user.kyc_level,
            }
          : null,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// Escuchar eventos de logout desde el API client
if (typeof window !== "undefined") {
  window.addEventListener("auth:logout", () => {
    useAuthStore.getState().logout();
  });
}
