"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Bell,
  Check,
  CheckCheck,
  Trash2,
  Wifi,
  WifiOff,
  AlertCircle,
  CheckCircle2,
  Info,
  AlertTriangle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { formatRelativeTime } from "@/lib/utils";
import { useNotifications, type Notification } from "@/providers/notifications-provider";

const priorityIcons = {
  low: Info,
  medium: Info,
  high: AlertTriangle,
  critical: AlertCircle,
};

const typeIcons: Record<string, typeof CheckCircle2> = {
  remittance_completed: CheckCircle2,
  remittance_failed: AlertCircle,
  kyc_status_change: Info,
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

function NotificationItem({
  notification,
  onMarkAsRead,
}: {
  notification: Notification;
  onMarkAsRead: (id: string) => void;
}) {
  const Icon = typeIcons[notification.type] || priorityIcons[notification.priority];
  const isError = notification.type.includes("failed") || notification.priority === "critical";
  const isSuccess = notification.type.includes("completed") || notification.type === "success";

  // Determinar URL de navegación
  const getHref = () => {
    if (notification.type.includes("remittance") && notification.data?.remittance_id) {
      return `/remittances/${notification.data.remittance_id}`;
    }
    if (notification.type === "kyc_status_change") {
      return "/verify-kyc";
    }
    return null;
  };

  const href = getHref();
  const content = (
    <div
      className={`flex gap-3 p-3 rounded-lg transition-colors ${
        notification.read ? "opacity-60" : "bg-muted/50"
      } hover:bg-muted`}
    >
      <div
        className={`h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          isError
            ? "bg-red-100 text-red-600 dark:bg-red-900/30"
            : isSuccess
            ? "bg-green-100 text-green-600 dark:bg-green-900/30"
            : "bg-primary/10 text-primary"
        }`}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{notification.title}</p>
        <p className="text-xs text-muted-foreground line-clamp-2">
          {notification.message}
        </p>
        <p className="text-[10px] text-muted-foreground mt-1">
          {formatRelativeTime(notification.timestamp)}
        </p>
      </div>
      {!notification.read && (
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onMarkAsRead(notification.id);
          }}
          className="h-6 w-6 flex items-center justify-center rounded hover:bg-background"
          title="Marcar como leída"
        >
          <Check className="h-3 w-3" />
        </button>
      )}
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }

  return content;
}

export function NotificationsDropdown() {
  const [open, setOpen] = useState(false);
  const {
    notifications,
    unreadCount,
    connectionStatus,
    markAsRead,
    markAllAsRead,
    clearNotifications,
  } = useNotifications();

  const isConnected = connectionStatus === "connected";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground flex items-center justify-center">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold">Notificaciones</h3>
            {isConnected ? (
              <Wifi className="h-3 w-3 text-green-500" />
            ) : (
              <WifiOff className="h-3 w-3 text-muted-foreground" />
            )}
          </div>
          <div className="flex items-center gap-1">
            {unreadCount > 0 && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={markAllAsRead}
                title="Marcar todas como leídas"
              >
                <CheckCheck className="h-4 w-4" />
              </Button>
            )}
            {notifications.length > 0 && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={clearNotifications}
                title="Limpiar todas"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Notifications List */}
        <ScrollArea className="h-[300px]">
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[200px] text-center p-4">
              <Bell className="h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">
                No tienes notificaciones
              </p>
              {!isConnected && (
                <p className="text-xs text-muted-foreground mt-1">
                  Conectando al servidor...
                </p>
              )}
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {notifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onMarkAsRead={markAsRead}
                />
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Footer */}
        {notifications.length > 0 && (
          <>
            <Separator />
            <div className="p-2">
              <Link href="/notifications" onClick={() => setOpen(false)}>
                <Button variant="ghost" className="w-full text-sm">
                  Ver todas las notificaciones
                </Button>
              </Link>
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
