/**
 * Setup de tests para Vitest.
 * Configura el entorno de testing para React y Zustand.
 */
import "@testing-library/jest-dom";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Cleanup despues de cada test
afterEach(() => {
  cleanup();
});

// Mock de localStorage que persiste valores
class LocalStorageMock implements Storage {
  private store: Record<string, string> = {};

  get length(): number {
    return Object.keys(this.store).length;
  }

  key(index: number): string | null {
    const keys = Object.keys(this.store);
    return keys[index] ?? null;
  }

  getItem(key: string): string | null {
    return this.store[key] ?? null;
  }

  setItem(key: string, value: string): void {
    this.store[key] = value;
  }

  removeItem(key: string): void {
    delete this.store[key];
  }

  clear(): void {
    this.store = {};
  }
}

global.localStorage = new LocalStorageMock();
global.sessionStorage = new LocalStorageMock();

// Mock de fetch
global.fetch = vi.fn();

// Mock de WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    // Simular conexion exitosa
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event("open"));
      }
    }, 0);
  }

  send(_data: string): void {
    // Mock send
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent("close", { code: code || 1000, reason }));
    }
  }
}

global.WebSocket = MockWebSocket as unknown as typeof WebSocket;

// Mock de Audio
class MockAudio {
  src: string = "";
  volume: number = 1;

  constructor(src?: string) {
    if (src) this.src = src;
  }

  play(): Promise<void> {
    return Promise.resolve();
  }
}

global.Audio = MockAudio as unknown as typeof Audio;

// Mock de Notification
const notificationMock = {
  permission: "granted" as NotificationPermission,
  requestPermission: vi.fn(() => Promise.resolve("granted" as NotificationPermission)),
};

Object.defineProperty(global, "Notification", {
  value: vi.fn().mockImplementation(() => ({})),
  writable: true,
});
Object.assign(global.Notification, notificationMock);

// Mock de matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock de ResizeObserver
class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

global.ResizeObserver = ResizeObserverMock;

// Mock de IntersectionObserver
class IntersectionObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

global.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;

// Helper para resetear stores de Zustand
export const resetAllStores = () => {
  // Los stores de Zustand se resetean con su estado inicial en cada test
};

// Helper para crear mock de respuesta fetch
export const createFetchResponse = <T>(data: T, ok = true, status = 200) => {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response);
};
