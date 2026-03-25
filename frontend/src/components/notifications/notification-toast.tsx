"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Info,
  AlertCircle,
  CheckCircle,
  Shield,
  Coins,
  FileSearch,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  useNotificationStore,
  Notification,
  NotificationType,
} from "@/store/notification-store";

// Iconos por tipo
const getIcon = (type: NotificationType) => {
  switch (type) {
    case "audit_started":
    case "audit_completed":
    case "audit_failed":
    case "audit_finding":
      return FileSearch;
    case "compliance_alert":
    case "kyc_status_change":
    case "risk_alert":
      return Shield;
    case "investment_received":
    case "investment_confirmed":
    case "dividend_available":
      return Coins;
    case "warning":
      return AlertTriangle;
    case "error":
      return AlertCircle;
    case "success":
      return CheckCircle;
    default:
      return Info;
  }
};

// Colores por prioridad
const getColors = (priority: string) => {
  switch (priority) {
    case "critical":
      return {
        bg: "bg-red-500/10 border-red-500/50",
        icon: "text-red-500",
        text: "text-red-900 dark:text-red-100",
      };
    case "high":
      return {
        bg: "bg-orange-500/10 border-orange-500/50",
        icon: "text-orange-500",
        text: "text-orange-900 dark:text-orange-100",
      };
    case "medium":
      return {
        bg: "bg-blue-500/10 border-blue-500/50",
        icon: "text-blue-500",
        text: "text-blue-900 dark:text-blue-100",
      };
    default:
      return {
        bg: "bg-gray-500/10 border-gray-500/50",
        icon: "text-gray-500",
        text: "text-gray-900 dark:text-gray-100",
      };
  }
};

interface ToastNotification extends Notification {
  showUntil: number;
}

export function NotificationToastProvider() {
  const [toasts, setToasts] = useState<ToastNotification[]>([]);
  const { notifications } = useNotificationStore();

  // Escuchar nuevas notificaciones
  useEffect(() => {
    if (notifications.length === 0) return;

    const latestNotification = notifications[0];

    // Verificar si ya mostramos esta notificacion
    if (toasts.some((t) => t.id === latestNotification.id)) return;

    // Agregar nuevo toast
    const newToast: ToastNotification = {
      ...latestNotification,
      showUntil: Date.now() + getDuration(latestNotification.priority),
    };

    setToasts((prev) => [newToast, ...prev].slice(0, 3)); // Max 3 toasts
  }, [notifications, toasts]);

  // Auto-remover toasts expirados
  useEffect(() => {
    const interval = setInterval(() => {
      setToasts((prev) => prev.filter((t) => t.showUntil > Date.now()));
    }, 500);

    return () => clearInterval(interval);
  }, []);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-96">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <Toast key={toast.id} notification={toast} onClose={removeToast} />
        ))}
      </AnimatePresence>
    </div>
  );
}

function getDuration(priority: string): number {
  switch (priority) {
    case "critical":
      return 10000; // 10 segundos
    case "high":
      return 7000;
    case "medium":
      return 5000;
    default:
      return 4000;
  }
}

function Toast({
  notification,
  onClose,
}: {
  notification: ToastNotification;
  onClose: (id: string) => void;
}) {
  const Icon = getIcon(notification.notification_type);
  const colors = getColors(notification.priority);

  // Progress bar
  const [progress, setProgress] = useState(100);
  const duration = getDuration(notification.priority);

  useEffect(() => {
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, 100 - (elapsed / duration) * 100);
      setProgress(remaining);
      if (remaining === 0) {
        clearInterval(interval);
      }
    }, 50);

    return () => clearInterval(interval);
  }, [duration]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 100, scale: 0.95 }}
      transition={{ type: "spring", damping: 25, stiffness: 300 }}
      className={cn(
        "relative overflow-hidden rounded-lg border shadow-lg backdrop-blur-sm",
        colors.bg
      )}
    >
      {/* Progress bar */}
      <div
        className="absolute bottom-0 left-0 h-1 bg-current opacity-30 transition-all"
        style={{ width: `${progress}%` }}
      />

      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className={cn("mt-0.5", colors.icon)}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <p className={cn("text-sm font-semibold", colors.text)}>
              {notification.title}
            </p>
            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
              {notification.message}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 -mt-1 -mr-2"
            onClick={() => onClose(notification.id)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
