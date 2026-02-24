/**
 * Store de autenticacion con Zustand
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { User, TokenResponse } from "@/types";
import { authAPI } from "@/lib/api-client";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  mfaPending: boolean;
  mfaToken: string | null;

  // Actions
  login: (email: string, password: string) => Promise<boolean>;
  verifyMFA: (code: string) => Promise<boolean>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  setUser: (user: User | null) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      mfaPending: false,
      mfaToken: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const response: TokenResponse = await authAPI.login(email, password);

          if (response.mfa_required) {
            set({
              mfaPending: true,
              mfaToken: response.mfa_token || null,
              isLoading: false,
            });
            return false; // Indica que se requiere MFA
          }

          // Login exitoso sin MFA
          localStorage.setItem("access_token", response.access_token);
          localStorage.setItem("refresh_token", response.refresh_token);

          // Obtener datos del usuario
          const user = await authAPI.getCurrentUser();
          set({
            user,
            isAuthenticated: true,
            isLoading: false,
            mfaPending: false,
            mfaToken: null,
          });

          return true;
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      verifyMFA: async (code: string) => {
        const { mfaToken } = get();
        if (!mfaToken) throw new Error("No hay sesion MFA pendiente");

        set({ isLoading: true });
        try {
          const response: TokenResponse = await authAPI.verifyMFA(
            code,
            mfaToken
          );

          localStorage.setItem("access_token", response.access_token);
          localStorage.setItem("refresh_token", response.refresh_token);

          const user = await authAPI.getCurrentUser();
          set({
            user,
            isAuthenticated: true,
            isLoading: false,
            mfaPending: false,
            mfaToken: null,
          });

          return true;
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        try {
          await authAPI.logout();
        } catch (error) {
          // Ignorar error, limpiar estado de todas formas
        }
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        set({
          user: null,
          isAuthenticated: false,
          mfaPending: false,
          mfaToken: null,
        });
      },

      fetchUser: async () => {
        const token = localStorage.getItem("access_token");
        if (!token) {
          set({ isAuthenticated: false, user: null });
          return;
        }

        set({ isLoading: true });
        try {
          const user = await authAPI.getCurrentUser();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch (error) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          set({ user: null, isAuthenticated: false, isLoading: false });
        }
      },

      setUser: (user) => set({ user, isAuthenticated: !!user }),
    }),
    {
      name: "fincore-auth",
      partialize: (state) => ({
        // Solo persistir estos campos
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
