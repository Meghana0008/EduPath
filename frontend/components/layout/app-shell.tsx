"use client";

import { useAuth } from "@/lib/auth-context";
import { Sidebar } from "./sidebar";
import { NotificationCenter } from "@/components/notifications/notification-center";
import { LoadingSpinner } from "@/components/ui/page-header";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { loading, user } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-ocean-gradient bg-grid-pattern bg-grid">
        <LoadingSpinner />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen flex bg-ocean-gradient bg-grid-pattern bg-grid">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 lg:ml-0">
        <header className="sticky top-0 z-30 flex items-center justify-end gap-3 px-4 sm:px-8 py-4 lg:py-5 bg-white/40 backdrop-blur-md border-b border-ocean-100/50">
          <NotificationCenter />
        </header>
        <main className="flex-1 px-4 sm:px-8 py-6 sm:py-8 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
