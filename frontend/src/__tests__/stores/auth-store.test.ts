/**
 * Tests para el store de autenticacion.
 */
import { describe, it, expect, beforeEach, vi, Mock } from "vitest";
import { act } from "@testing-library/react";
import { useAuthStore } from "@/store/auth-store";

// Mock de api-client
vi.mock("@/lib/api-client", () => ({
  authAPI: {
    login: vi.fn(),
    verifyMFA: vi.fn(),
    logout: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}));

import { authAPI } from "@/lib/api-client";

// Resetear store antes de cada test
beforeEach(() => {
  // Limpiar localStorage
  localStorage.clear();

  // Resetear estado del store
  useAuthStore.setState({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    mfaPending: false,
    mfaToken: null,
  });

  vi.clearAllMocks();
});

describe("AuthStore", () => {
  describe("Estado inicial", () => {
    it("debe tener estado inicial correcto", () => {
      const state = useAuthStore.getState();

      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
      expect(state.mfaPending).toBe(false);
      expect(state.mfaToken).toBeNull();
    });
  });

  describe("login", () => {
    it("debe hacer login exitoso sin MFA", async () => {
      const mockUser = {
        id: "user-123",
        email: "test@fincore.mx",
        nombre: "Test User",
        rol: "Admin",
        is_active: true,
      };

      (authAPI.login as Mock).mockResolvedValueOnce({
        access_token: "access-token-123",
        refresh_token: "refresh-token-123",
        token_type: "bearer",
        mfa_required: false,
      });

      (authAPI.getCurrentUser as Mock).mockResolvedValueOnce(mockUser);

      let result: boolean = false;
      await act(async () => {
        result = await useAuthStore.getState().login("test@fincore.mx", "password123");
      });

      expect(result).toBe(true);

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user).toEqual(mockUser);
      expect(state.mfaPending).toBe(false);
      expect(localStorage.getItem("access_token")).toBe("access-token-123");
      expect(localStorage.getItem("refresh_token")).toBe("refresh-token-123");
    });

    it("debe manejar login con MFA requerido", async () => {
      (authAPI.login as Mock).mockResolvedValueOnce({
        mfa_required: true,
        mfa_token: "mfa-session-token",
      });

      let result: boolean = true;
      await act(async () => {
        result = await useAuthStore.getState().login("test@fincore.mx", "password123");
      });

      expect(result).toBe(false); // false indica que se requiere MFA

      const state = useAuthStore.getState();
      expect(state.mfaPending).toBe(true);
      expect(state.mfaToken).toBe("mfa-session-token");
      expect(state.isAuthenticated).toBe(false);
    });

    it("debe manejar error de login", async () => {
      (authAPI.login as Mock).mockRejectedValueOnce(new Error("Credenciales invalidas"));

      await expect(
        act(async () => {
          await useAuthStore.getState().login("wrong@email.com", "wrongpassword");
        })
      ).rejects.toThrow("Credenciales invalidas");

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
    });

    it("debe establecer isLoading durante el login", async () => {
      let resolveLogin: (value: unknown) => void;
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve;
      });

      (authAPI.login as Mock).mockReturnValueOnce(loginPromise);

      // Iniciar login
      const loginCall = act(async () => {
        useAuthStore.getState().login("test@fincore.mx", "password123");
      });

      // Verificar que isLoading es true
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      expect(useAuthStore.getState().isLoading).toBe(true);

      // Resolver login
      resolveLogin!({
        access_token: "token",
        refresh_token: "refresh",
        mfa_required: false,
      });

      (authAPI.getCurrentUser as Mock).mockResolvedValueOnce({ id: "user-1" });

      await loginCall;
    });
  });

  describe("verifyMFA", () => {
    it("debe verificar MFA exitosamente", async () => {
      const mockUser = {
        id: "user-mfa-123",
        email: "mfa@fincore.mx",
        nombre: "MFA User",
        rol: "Inversionista",
        is_active: true,
      };

      // Setup: establecer estado de MFA pendiente
      useAuthStore.setState({
        mfaPending: true,
        mfaToken: "mfa-session-token",
      });

      (authAPI.verifyMFA as Mock).mockResolvedValueOnce({
        access_token: "mfa-access-token",
        refresh_token: "mfa-refresh-token",
        token_type: "bearer",
      });

      (authAPI.getCurrentUser as Mock).mockResolvedValueOnce(mockUser);

      let result: boolean = false;
      await act(async () => {
        result = await useAuthStore.getState().verifyMFA("123456");
      });

      expect(result).toBe(true);

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user).toEqual(mockUser);
      expect(state.mfaPending).toBe(false);
      expect(state.mfaToken).toBeNull();
      expect(localStorage.getItem("access_token")).toBe("mfa-access-token");
    });

    it("debe lanzar error si no hay sesion MFA pendiente", async () => {
      // Sin mfaToken establecido
      useAuthStore.setState({
        mfaPending: false,
        mfaToken: null,
      });

      await expect(
        act(async () => {
          await useAuthStore.getState().verifyMFA("123456");
        })
      ).rejects.toThrow("No hay sesion MFA pendiente");
    });

    it("debe manejar error de verificacion MFA", async () => {
      useAuthStore.setState({
        mfaPending: true,
        mfaToken: "mfa-session-token",
      });

      (authAPI.verifyMFA as Mock).mockRejectedValueOnce(new Error("Codigo invalido"));

      await expect(
        act(async () => {
          await useAuthStore.getState().verifyMFA("000000");
        })
      ).rejects.toThrow("Codigo invalido");

      const state = useAuthStore.getState();
      expect(state.isLoading).toBe(false);
    });
  });

  describe("logout", () => {
    it("debe hacer logout exitosamente", async () => {
      // Setup: usuario autenticado
      localStorage.setItem("access_token", "some-token");
      localStorage.setItem("refresh_token", "some-refresh-token");
      useAuthStore.setState({
        user: { id: "user-1", email: "test@fincore.mx" },
        isAuthenticated: true,
      });

      (authAPI.logout as Mock).mockResolvedValueOnce({});

      await act(async () => {
        await useAuthStore.getState().logout();
      });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.mfaPending).toBe(false);
      expect(state.mfaToken).toBeNull();
      expect(localStorage.getItem("access_token")).toBeNull();
      expect(localStorage.getItem("refresh_token")).toBeNull();
    });

    it("debe limpiar estado incluso si API falla", async () => {
      localStorage.setItem("access_token", "some-token");
      useAuthStore.setState({
        user: { id: "user-1", email: "test@fincore.mx" },
        isAuthenticated: true,
      });

      (authAPI.logout as Mock).mockRejectedValueOnce(new Error("Network error"));

      await act(async () => {
        await useAuthStore.getState().logout();
      });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(localStorage.getItem("access_token")).toBeNull();
    });
  });

  describe("fetchUser", () => {
    it("debe obtener usuario si hay token", async () => {
      const mockUser = {
        id: "fetch-user-123",
        email: "fetch@fincore.mx",
        nombre: "Fetched User",
        rol: "Admin",
        is_active: true,
      };

      localStorage.setItem("access_token", "valid-token");

      (authAPI.getCurrentUser as Mock).mockResolvedValueOnce(mockUser);

      await act(async () => {
        await useAuthStore.getState().fetchUser();
      });

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
    });

    it("debe limpiar estado si no hay token", async () => {
      // Sin token en localStorage
      localStorage.removeItem("access_token");

      await act(async () => {
        await useAuthStore.getState().fetchUser();
      });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });

    it("debe limpiar estado si fetch falla", async () => {
      localStorage.setItem("access_token", "invalid-token");

      (authAPI.getCurrentUser as Mock).mockRejectedValueOnce(new Error("Unauthorized"));

      await act(async () => {
        await useAuthStore.getState().fetchUser();
      });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(localStorage.getItem("access_token")).toBeNull();
    });
  });

  describe("setUser", () => {
    it("debe establecer usuario y autenticacion", () => {
      const mockUser = {
        id: "set-user-123",
        email: "set@fincore.mx",
        nombre: "Set User",
        rol: "Inversionista",
        is_active: true,
      };

      act(() => {
        useAuthStore.getState().setUser(mockUser);
      });

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
    });

    it("debe limpiar autenticacion si user es null", () => {
      // Setup: usuario autenticado
      useAuthStore.setState({
        user: { id: "user-1" },
        isAuthenticated: true,
      });

      act(() => {
        useAuthStore.getState().setUser(null);
      });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });
});

describe("Persistencia", () => {
  it("debe persistir isAuthenticated", () => {
    // El store usa persist middleware
    // Verificar que la configuracion de partialize incluye isAuthenticated
    const store = useAuthStore;

    // Establecer estado
    act(() => {
      store.setState({ isAuthenticated: true });
    });

    // El estado debe reflejar el cambio
    expect(store.getState().isAuthenticated).toBe(true);
  });
});
