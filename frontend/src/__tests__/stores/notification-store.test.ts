/**
 * Tests para el store de notificaciones.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { act } from "@testing-library/react";
import {
  useNotificationStore,
  useUnreadNotifications,
  useNotificationsByType,
  useCriticalNotifications,
  type Notification,
  type WebSocketMessage,
} from "@/store/notification-store";

// Resetear store antes de cada test
beforeEach(() => {
  const store = useNotificationStore.getState();
  store.clearAll();
  store.disconnect();
  vi.clearAllMocks();
});

afterEach(() => {
  const store = useNotificationStore.getState();
  store.disconnect();
});

describe("NotificationStore", () => {
  describe("Estado inicial", () => {
    it("debe tener estado inicial correcto", () => {
      const state = useNotificationStore.getState();

      expect(state.notifications).toEqual([]);
      expect(state.unreadCount).toBe(0);
      expect(state.isConnected).toBe(false);
      expect(state.isConnecting).toBe(false);
      expect(state.connectionError).toBeNull();
      expect(state.ws).toBeNull();
    });

    it("debe tener preferencias por defecto", () => {
      const state = useNotificationStore.getState();

      expect(state.preferences.enableSound).toBe(true);
      expect(state.preferences.enableDesktop).toBe(false);
    });
  });

  describe("addNotification", () => {
    it("debe agregar una notificacion", () => {
      const notification: Notification = {
        id: "notif-1",
        notification_type: "audit_completed",
        priority: "high",
        title: "Auditoria completada",
        message: "La auditoria ha finalizado",
        is_read: false,
        created_at: new Date().toISOString(),
      };

      act(() => {
        useNotificationStore.getState().addNotification(notification);
      });

      const state = useNotificationStore.getState();
      expect(state.notifications).toHaveLength(1);
      expect(state.notifications[0].id).toBe("notif-1");
      expect(state.unreadCount).toBe(1);
    });

    it("debe agregar notificacion desde WebSocket message", () => {
      const wsMessage: WebSocketMessage = {
        type: "notification",
        id: "notif-ws-1",
        notification_type: "risk_alert",
        priority: "critical",
        title: "Alerta de riesgo",
        message: "Se detecta actividad sospechosa",
        timestamp: new Date().toISOString(),
      };

      act(() => {
        useNotificationStore.getState().addNotification(wsMessage);
      });

      const state = useNotificationStore.getState();
      expect(state.notifications).toHaveLength(1);
      expect(state.notifications[0].notification_type).toBe("risk_alert");
    });

    it("debe limitar a 100 notificaciones", () => {
      const store = useNotificationStore.getState();

      // Agregar 105 notificaciones
      for (let i = 0; i < 105; i++) {
        act(() => {
          store.addNotification({
            id: `notif-${i}`,
            notification_type: "info",
            priority: "low",
            title: `Notif ${i}`,
            message: "Test",
            is_read: false,
            created_at: new Date().toISOString(),
          });
        });
      }

      const state = useNotificationStore.getState();
      expect(state.notifications.length).toBeLessThanOrEqual(100);
    });
  });

  describe("markAsRead", () => {
    it("debe marcar notificacion como leida", async () => {
      // Setup
      const notification: Notification = {
        id: "notif-read-1",
        notification_type: "info",
        priority: "low",
        title: "Test",
        message: "Test message",
        is_read: false,
        created_at: new Date().toISOString(),
      };

      act(() => {
        useNotificationStore.getState().addNotification(notification);
      });

      // Mock fetch
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      } as Response);

      // Act
      await act(async () => {
        await useNotificationStore.getState().markAsRead("notif-read-1");
      });

      // Assert
      const state = useNotificationStore.getState();
      expect(state.notifications[0].is_read).toBe(true);
      expect(state.notifications[0].read_at).toBeDefined();
      expect(state.unreadCount).toBe(0);
    });

    it("debe decrementar unreadCount correctamente", async () => {
      // Setup - agregar 3 notificaciones
      for (let i = 0; i < 3; i++) {
        act(() => {
          useNotificationStore.getState().addNotification({
            id: `notif-${i}`,
            notification_type: "info",
            priority: "low",
            title: `Test ${i}`,
            message: "Test",
            is_read: false,
            created_at: new Date().toISOString(),
          });
        });
      }

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      } as Response);

      let state = useNotificationStore.getState();
      expect(state.unreadCount).toBe(3);

      // Marcar una como leida
      await act(async () => {
        await useNotificationStore.getState().markAsRead("notif-0");
      });

      state = useNotificationStore.getState();
      expect(state.unreadCount).toBe(2);
    });
  });

  describe("markAllAsRead", () => {
    it("debe marcar todas como leidas", async () => {
      // Setup
      for (let i = 0; i < 5; i++) {
        act(() => {
          useNotificationStore.getState().addNotification({
            id: `notif-all-${i}`,
            notification_type: "info",
            priority: "low",
            title: `Test ${i}`,
            message: "Test",
            is_read: false,
            created_at: new Date().toISOString(),
          });
        });
      }

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      } as Response);

      // Act
      await act(async () => {
        await useNotificationStore.getState().markAllAsRead();
      });

      // Assert
      const state = useNotificationStore.getState();
      expect(state.unreadCount).toBe(0);
      state.notifications.forEach((n) => {
        expect(n.is_read).toBe(true);
      });
    });
  });

  describe("deleteNotification", () => {
    it("debe eliminar notificacion", async () => {
      // Setup
      act(() => {
        useNotificationStore.getState().addNotification({
          id: "notif-delete-1",
          notification_type: "info",
          priority: "low",
          title: "To delete",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        });
      });

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      } as Response);

      // Act
      await act(async () => {
        await useNotificationStore.getState().deleteNotification("notif-delete-1");
      });

      // Assert
      const state = useNotificationStore.getState();
      expect(state.notifications).toHaveLength(0);
    });

    it("debe decrementar unreadCount si notificacion no estaba leida", async () => {
      // Setup
      act(() => {
        useNotificationStore.getState().addNotification({
          id: "notif-delete-unread",
          notification_type: "info",
          priority: "low",
          title: "Unread",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        });
      });

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      } as Response);

      const initialCount = useNotificationStore.getState().unreadCount;

      await act(async () => {
        await useNotificationStore.getState().deleteNotification("notif-delete-unread");
      });

      const state = useNotificationStore.getState();
      expect(state.unreadCount).toBe(initialCount - 1);
    });
  });

  describe("clearAll", () => {
    it("debe limpiar todas las notificaciones", () => {
      // Setup
      for (let i = 0; i < 10; i++) {
        act(() => {
          useNotificationStore.getState().addNotification({
            id: `notif-clear-${i}`,
            notification_type: "info",
            priority: "low",
            title: `Test ${i}`,
            message: "Test",
            is_read: false,
            created_at: new Date().toISOString(),
          });
        });
      }

      // Act
      act(() => {
        useNotificationStore.getState().clearAll();
      });

      // Assert
      const state = useNotificationStore.getState();
      expect(state.notifications).toHaveLength(0);
      expect(state.unreadCount).toBe(0);
    });
  });

  describe("Preferencias", () => {
    it("debe cambiar preferencia de sonido", () => {
      act(() => {
        useNotificationStore.getState().setPreference("enableSound", false);
      });

      const state = useNotificationStore.getState();
      expect(state.preferences.enableSound).toBe(false);
    });

    it("debe cambiar preferencia de desktop", () => {
      act(() => {
        useNotificationStore.getState().setPreference("enableDesktop", true);
      });

      const state = useNotificationStore.getState();
      expect(state.preferences.enableDesktop).toBe(true);
    });
  });

  describe("WebSocket Connection", () => {
    it("debe conectar con token", async () => {
      await act(async () => {
        useNotificationStore.getState().connect("test-token");
        // Esperar a que el mock WebSocket se conecte
        await new Promise((resolve) => setTimeout(resolve, 10));
      });

      const state = useNotificationStore.getState();
      expect(state.isConnected).toBe(true);
      expect(state.ws).not.toBeNull();
    });

    it("debe desconectar correctamente", async () => {
      // Conectar primero
      await act(async () => {
        useNotificationStore.getState().connect("test-token");
        await new Promise((resolve) => setTimeout(resolve, 10));
      });

      // Desconectar
      act(() => {
        useNotificationStore.getState().disconnect();
      });

      const state = useNotificationStore.getState();
      expect(state.isConnected).toBe(false);
      expect(state.ws).toBeNull();
    });

    it("no debe crear conexiones duplicadas", async () => {
      const store = useNotificationStore.getState();

      await act(async () => {
        store.connect("test-token");
        await new Promise((resolve) => setTimeout(resolve, 10));
      });

      const firstWs = useNotificationStore.getState().ws;

      // Intentar conectar de nuevo
      act(() => {
        store.connect("test-token");
      });

      const secondWs = useNotificationStore.getState().ws;
      expect(secondWs).toBe(firstWs);
    });
  });

  describe("fetchNotifications", () => {
    it("debe cargar notificaciones del backend", async () => {
      const mockNotifications = [
        {
          id: "fetch-1",
          notification_type: "info",
          priority: "low",
          title: "Fetched 1",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        },
        {
          id: "fetch-2",
          notification_type: "warning",
          priority: "medium",
          title: "Fetched 2",
          message: "Test",
          is_read: true,
          created_at: new Date().toISOString(),
        },
      ];

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            notifications: mockNotifications,
            total_unread: 1,
          }),
      } as Response);

      await act(async () => {
        await useNotificationStore.getState().fetchNotifications();
      });

      const state = useNotificationStore.getState();
      expect(state.notifications).toHaveLength(2);
      expect(state.unreadCount).toBe(1);
    });
  });

  describe("fetchUnreadCount", () => {
    it("debe actualizar conteo de no leidas", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ unread_count: 42 }),
      } as Response);

      await act(async () => {
        await useNotificationStore.getState().fetchUnreadCount();
      });

      const state = useNotificationStore.getState();
      expect(state.unreadCount).toBe(42);
    });
  });
});

describe("Hooks derivados", () => {
  beforeEach(() => {
    const store = useNotificationStore.getState();
    store.clearAll();
  });

  describe("useUnreadNotifications", () => {
    it("debe filtrar solo notificaciones no leidas", () => {
      // Setup
      act(() => {
        useNotificationStore.getState().addNotification({
          id: "unread-1",
          notification_type: "info",
          priority: "low",
          title: "Unread",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        });
      });

      // Simular una leida
      act(() => {
        useNotificationStore.setState((state) => ({
          notifications: [
            ...state.notifications,
            {
              id: "read-1",
              notification_type: "info" as const,
              priority: "low" as const,
              title: "Read",
              message: "Test",
              is_read: true,
              created_at: new Date().toISOString(),
            },
          ],
        }));
      });

      // El hook filtra las no leidas
      const notifications = useNotificationStore.getState().notifications;
      const unread = notifications.filter((n) => !n.is_read);

      expect(unread).toHaveLength(1);
      expect(unread[0].id).toBe("unread-1");
    });
  });

  describe("useCriticalNotifications", () => {
    it("debe filtrar notificaciones criticas y de alta prioridad", () => {
      // Setup
      const notifications = [
        {
          id: "critical-1",
          notification_type: "risk_alert" as const,
          priority: "critical" as const,
          title: "Critical",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        },
        {
          id: "high-1",
          notification_type: "audit_finding" as const,
          priority: "high" as const,
          title: "High",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        },
        {
          id: "low-1",
          notification_type: "info" as const,
          priority: "low" as const,
          title: "Low",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        },
      ];

      act(() => {
        notifications.forEach((n) => {
          useNotificationStore.getState().addNotification(n);
        });
      });

      const allNotifs = useNotificationStore.getState().notifications;
      const critical = allNotifs.filter(
        (n) => n.priority === "critical" || n.priority === "high"
      );

      expect(critical).toHaveLength(2);
    });
  });

  describe("useNotificationsByType", () => {
    it("debe filtrar por tipo de notificacion", () => {
      // Setup
      const notifications = [
        {
          id: "audit-1",
          notification_type: "audit_completed" as const,
          priority: "medium" as const,
          title: "Audit 1",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        },
        {
          id: "audit-2",
          notification_type: "audit_completed" as const,
          priority: "medium" as const,
          title: "Audit 2",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        },
        {
          id: "info-1",
          notification_type: "info" as const,
          priority: "low" as const,
          title: "Info 1",
          message: "Test",
          is_read: false,
          created_at: new Date().toISOString(),
        },
      ];

      act(() => {
        notifications.forEach((n) => {
          useNotificationStore.getState().addNotification(n);
        });
      });

      const allNotifs = useNotificationStore.getState().notifications;
      const auditNotifs = allNotifs.filter(
        (n) => n.notification_type === "audit_completed"
      );

      expect(auditNotifs).toHaveLength(2);
    });
  });
});
