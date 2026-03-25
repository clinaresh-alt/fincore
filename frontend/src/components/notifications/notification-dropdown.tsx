"use client";

import { useEffect, useState, useRef } from "react";
import { formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";
import {
  Bell,
  BellRing,
  Check,
  CheckCheck,
  Trash2,
  AlertTriangle,
  Info,
  AlertCircle,
  CheckCircle,
  Shield,
  Coins,
  FileSearch,
  Settings,
  Wifi,
  WifiOff,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  useNotificationStore,
  Notification,
  NotificationType,
} from "@/store/notification-store";
import { useAuthStore } from "@/store/auth-store";
import Link from "next/link";

// Helper para obtener token
const getToken = () => {
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token");
  }
  return null;
};

// Iconos por tipo de notificacion
const getNotificationIcon = (type: NotificationType) => {
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
const getPriorityColor = (priority: string) => {
  switch (priority) {
    case "critical":
      return "text-red-500 bg-red-500/10";
    case "high":
      return "text-orange-500 bg-orange-500/10";
    case "medium":
      return "text-blue-500 bg-blue-500/10";
    default:
      return "text-gray-500 bg-gray-500/10";
  }
};

// Componente de item de notificacion
function NotificationItem({
  notification,
  onRead,
  onDelete,
}: {
  notification: Notification;
  onRead: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const Icon = getNotificationIcon(notification.notification_type);
  const priorityColor = getPriorityColor(notification.priority);

  return (
    <div
      className={cn(
        "flex items-start gap-3 p-3 hover:bg-accent rounded-lg transition-colors cursor-pointer",
        !notification.is_read && "bg-accent/50"
      )}
      onClick={() => !notification.is_read && onRead(notification.id)}
    >
      <div className={cn("p-2 rounded-full", priorityColor)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className={cn("text-sm font-medium truncate", !notification.is_read && "font-semibold")}>
            {notification.title}
          </p>
          {notification.priority === "critical" && (
            <Badge variant="destructive" className="text-xs py-0">
              Critico
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
          {notification.message}
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          {formatDistanceToNow(new Date(notification.created_at), {
            addSuffix: true,
            locale: es,
          })}
        </p>
      </div>
      <div className="flex flex-col gap-1">
        {!notification.is_read && (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={(e) => {
              e.stopPropagation();
              onRead(notification.id);
            }}
          >
            <Check className="h-3 w-3" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-muted-foreground hover:text-destructive"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(notification.id);
          }}
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

export function NotificationDropdown() {
  const {
    notifications,
    unreadCount,
    isConnected,
    connect,
    disconnect,
    markAsRead,
    markAllAsRead,
    deleteNotification,
  } = useNotificationStore();

  const { isAuthenticated } = useAuthStore();
  const [isOpen, setIsOpen] = useState(false);
  const isMountedRef = useRef(true);
  const cleanupTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Conectar WebSocket cuando esta autenticado
  useEffect(() => {
    isMountedRef.current = true;

    // Cancelar cualquier desconexion pendiente (por StrictMode remount)
    if (cleanupTimeoutRef.current) {
      clearTimeout(cleanupTimeoutRef.current);
      cleanupTimeoutRef.current = null;
    }

    const token = getToken();
    if (isAuthenticated && token) {
      connect(token);
    }

    return () => {
      isMountedRef.current = false;
      // Delay para permitir que StrictMode vuelva a montar antes de desconectar
      cleanupTimeoutRef.current = setTimeout(() => {
        if (!isMountedRef.current) {
          disconnect();
        }
      }, 100);
    };
  }, [isAuthenticated, connect, disconnect]);

  // Agrupar notificaciones por fecha
  const groupedNotifications = notifications.reduce((groups, notification) => {
    const date = new Date(notification.created_at).toLocaleDateString();
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date].push(notification);
    return groups;
  }, {} as Record<string, Notification[]>);

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          {unreadCount > 0 ? (
            <BellRing className="h-5 w-5" />
          ) : (
            <Bell className="h-5 w-5" />
          )}
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
          {/* Indicador de conexion */}
          <span
            className={cn(
              "absolute bottom-0 right-0 h-2 w-2 rounded-full border border-background",
              isConnected ? "bg-green-500" : "bg-gray-400"
            )}
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-96">
        <DropdownMenuLabel className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            Notificaciones
            {isConnected ? (
              <Wifi className="h-3 w-3 text-green-500" />
            ) : (
              <WifiOff className="h-3 w-3 text-gray-400" />
            )}
          </span>
          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={(e) => {
                  e.preventDefault();
                  markAllAsRead();
                }}
              >
                <CheckCheck className="h-3 w-3 mr-1" />
                Marcar todas
              </Button>
            )}
            <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
              <Link href="/settings/notifications">
                <Settings className="h-3 w-3" />
              </Link>
            </Button>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        <ScrollArea className="h-[400px]">
          {notifications.length === 0 ? (
            <div className="p-8 text-center">
              <Bell className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">
                No tienes notificaciones
              </p>
            </div>
          ) : (
            <div className="p-2 space-y-4">
              {Object.entries(groupedNotifications).map(([date, notifs]) => (
                <div key={date}>
                  <p className="text-xs font-medium text-muted-foreground px-2 mb-2">
                    {date === new Date().toLocaleDateString() ? "Hoy" : date}
                  </p>
                  <div className="space-y-1">
                    {notifs.map((notification) => (
                      <NotificationItem
                        key={notification.id}
                        notification={notification}
                        onRead={markAsRead}
                        onDelete={deleteNotification}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        {notifications.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <div className="p-2">
              <Button variant="ghost" className="w-full text-sm" asChild>
                <Link href="/notifications">Ver todas las notificaciones</Link>
              </Button>
            </div>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
