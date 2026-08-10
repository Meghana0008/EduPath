"use client";

import { useEffect, useState } from "react";
import { Bell, X, CheckCheck } from "lucide-react";
import { api } from "@/lib/api";
import type { Notification } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);

  const unread = notifications.filter((n) => !n.read).length;

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.notifications();
      setNotifications(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const markRead = async (id: string) => {
    try {
      await api.markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: true } : n))
      );
    } catch {
      /* ignore */
    }
  };

  const markAllRead = async () => {
    const unreadItems = notifications.filter((n) => !n.read);
    await Promise.all(unreadItems.map((n) => api.markNotificationRead(n.id)));
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const priorityColor = (p: string) => {
    if (p === "high") return "border-l-red-400";
    if (p === "medium") return "border-l-gold-400";
    return "border-l-ocean-300";
  };

  return (
    <div className="relative">
      <button
        onClick={() => {
          setOpen(!open);
          if (!open) load();
        }}
        className="relative p-2.5 rounded-xl border border-ocean-100 bg-white/70 hover:bg-ocean-50 transition-colors"
        aria-label="Notifications"
      >
        <Bell className="w-5 h-5 text-ocean-700" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-gold-500 text-white text-[10px] font-bold flex items-center justify-center animate-pulse-soft">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-2 w-80 sm:w-96 z-50 rounded-2xl border border-ocean-100 bg-white/95 backdrop-blur-xl shadow-xl shadow-ocean-900/10 animate-slide-up overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-ocean-100">
              <h3 className="font-display font-semibold text-ocean-900">Notifications</h3>
              <div className="flex items-center gap-2">
                {unread > 0 && (
                  <button
                    onClick={markAllRead}
                    className="text-xs text-ocean-600 hover:text-ocean-800 flex items-center gap-1"
                  >
                    <CheckCheck className="w-3.5 h-3.5" />
                    Mark all read
                  </button>
                )}
                <button onClick={() => setOpen(false)} className="p-1 hover:bg-ocean-50 rounded-lg">
                  <X className="w-4 h-4 text-ocean-500" />
                </button>
              </div>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {loading && notifications.length === 0 ? (
                <p className="p-4 text-sm text-ocean-500 text-center">Loading...</p>
              ) : notifications.length === 0 ? (
                <p className="p-6 text-sm text-ocean-500 text-center">No notifications yet</p>
              ) : (
                notifications.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => !n.read && markRead(n.id)}
                    className={cn(
                      "w-full text-left px-4 py-3 border-b border-ocean-50 border-l-4 transition-colors",
                      priorityColor(n.priority),
                      !n.read ? "bg-ocean-50/50" : "bg-white hover:bg-ocean-50/30"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-ocean-900">{n.title}</p>
                      {!n.read && <Badge variant="ocean" className="text-[9px] shrink-0">New</Badge>}
                    </div>
                    <p className="text-xs text-ocean-600 mt-1 line-clamp-2">{n.message}</p>
                    <p className="text-[10px] text-ocean-400 mt-1.5">{formatDateTime(n.created_at)}</p>
                  </button>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
