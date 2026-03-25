/**
 * Tests para hooks personalizados
 */

import { describe, it, expect, beforeEach, vi } from "vitest";

// Mock de localStorage ya configurado en setup.ts

describe("localStorage functionality", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("almacena y recupera valores string", () => {
    localStorage.setItem("testKey", "testValue");
    expect(localStorage.getItem("testKey")).toBe("testValue");
  });

  it("almacena y recupera objetos JSON", () => {
    const obj = { name: "test", value: 123 };
    localStorage.setItem("jsonKey", JSON.stringify(obj));

    const retrieved = JSON.parse(localStorage.getItem("jsonKey") || "{}");
    expect(retrieved).toEqual(obj);
  });

  it("retorna null para keys inexistentes", () => {
    expect(localStorage.getItem("nonexistent")).toBeNull();
  });

  it("elimina items correctamente", () => {
    localStorage.setItem("toRemove", "value");
    localStorage.removeItem("toRemove");
    expect(localStorage.getItem("toRemove")).toBeNull();
  });

  it("limpia todo el storage", () => {
    localStorage.setItem("key1", "value1");
    localStorage.setItem("key2", "value2");
    localStorage.clear();

    expect(localStorage.length).toBe(0);
    expect(localStorage.getItem("key1")).toBeNull();
  });

  it("reporta length correcto", () => {
    expect(localStorage.length).toBe(0);

    localStorage.setItem("a", "1");
    expect(localStorage.length).toBe(1);

    localStorage.setItem("b", "2");
    expect(localStorage.length).toBe(2);

    localStorage.removeItem("a");
    expect(localStorage.length).toBe(1);
  });

  it("accede a keys por indice", () => {
    localStorage.setItem("first", "1");
    localStorage.setItem("second", "2");

    const keys = [localStorage.key(0), localStorage.key(1)];
    expect(keys).toContain("first");
    expect(keys).toContain("second");
  });

  it("retorna null para indice fuera de rango", () => {
    expect(localStorage.key(999)).toBeNull();
  });
});

describe("sessionStorage functionality", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("almacena y recupera valores", () => {
    sessionStorage.setItem("sessionKey", "sessionValue");
    expect(sessionStorage.getItem("sessionKey")).toBe("sessionValue");
  });

  it("es independiente de localStorage", () => {
    localStorage.setItem("shared", "local");
    sessionStorage.setItem("shared", "session");

    expect(localStorage.getItem("shared")).toBe("local");
    expect(sessionStorage.getItem("shared")).toBe("session");
  });
});

describe("Token management", () => {
  const TOKEN_KEY = "fincore_access_token";
  const REFRESH_KEY = "fincore_refresh_token";

  beforeEach(() => {
    localStorage.clear();
  });

  it("almacena access token", () => {
    const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test";
    localStorage.setItem(TOKEN_KEY, token);
    expect(localStorage.getItem(TOKEN_KEY)).toBe(token);
  });

  it("almacena refresh token", () => {
    const token = "refresh_token_value";
    localStorage.setItem(REFRESH_KEY, token);
    expect(localStorage.getItem(REFRESH_KEY)).toBe(token);
  });

  it("limpia tokens al logout", () => {
    localStorage.setItem(TOKEN_KEY, "access");
    localStorage.setItem(REFRESH_KEY, "refresh");

    // Simular logout
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it("verifica existencia de token", () => {
    const hasToken = () => localStorage.getItem(TOKEN_KEY) !== null;

    expect(hasToken()).toBe(false);

    localStorage.setItem(TOKEN_KEY, "token");
    expect(hasToken()).toBe(true);
  });
});

describe("User preferences storage", () => {
  const PREFS_KEY = "fincore_user_prefs";

  interface UserPrefs {
    theme: "light" | "dark";
    language: string;
    notifications: boolean;
  }

  beforeEach(() => {
    localStorage.clear();
  });

  it("almacena preferencias de usuario", () => {
    const prefs: UserPrefs = {
      theme: "dark",
      language: "es",
      notifications: true,
    };

    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
    const stored = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");

    expect(stored.theme).toBe("dark");
    expect(stored.language).toBe("es");
    expect(stored.notifications).toBe(true);
  });

  it("actualiza preferencias parcialmente", () => {
    const initial: UserPrefs = {
      theme: "light",
      language: "es",
      notifications: true,
    };
    localStorage.setItem(PREFS_KEY, JSON.stringify(initial));

    // Actualizar solo tema
    const current = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
    const updated = { ...current, theme: "dark" };
    localStorage.setItem(PREFS_KEY, JSON.stringify(updated));

    const result = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
    expect(result.theme).toBe("dark");
    expect(result.language).toBe("es"); // Sin cambios
  });

  it("usa valores por defecto cuando no hay datos", () => {
    const defaults: UserPrefs = {
      theme: "light",
      language: "es",
      notifications: true,
    };

    const stored = localStorage.getItem(PREFS_KEY);
    const prefs: UserPrefs = stored ? JSON.parse(stored) : defaults;

    expect(prefs).toEqual(defaults);
  });
});

describe("Data persistence patterns", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("persiste datos entre operaciones", () => {
    // Simular escritura
    localStorage.setItem("persistent", "data");

    // Simular lectura posterior
    const value = localStorage.getItem("persistent");

    expect(value).toBe("data");
  });

  it("maneja datos complejos", () => {
    const complexData = {
      user: {
        id: "123",
        name: "Test User",
        roles: ["admin", "user"],
      },
      settings: {
        nested: {
          deep: {
            value: true,
          },
        },
      },
      array: [1, 2, 3],
    };

    localStorage.setItem("complex", JSON.stringify(complexData));
    const retrieved = JSON.parse(localStorage.getItem("complex") || "{}");

    expect(retrieved.user.id).toBe("123");
    expect(retrieved.user.roles).toContain("admin");
    expect(retrieved.settings.nested.deep.value).toBe(true);
    expect(retrieved.array).toHaveLength(3);
  });

  it("maneja valores booleanos como string", () => {
    localStorage.setItem("boolTrue", "true");
    localStorage.setItem("boolFalse", "false");

    expect(localStorage.getItem("boolTrue")).toBe("true");
    expect(localStorage.getItem("boolFalse")).toBe("false");

    // Conversion a boolean
    expect(localStorage.getItem("boolTrue") === "true").toBe(true);
    expect(localStorage.getItem("boolFalse") === "true").toBe(false);
  });

  it("maneja numeros como string", () => {
    localStorage.setItem("number", "42");

    const strValue = localStorage.getItem("number");
    const numValue = Number(strValue);

    expect(strValue).toBe("42");
    expect(numValue).toBe(42);
  });
});
