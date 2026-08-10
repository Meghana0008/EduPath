"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  User,
  Compass,
  FileText,
  Calendar,
  Map,
  Bot,
  Settings,
  LogOut,
  Menu,
  X,
  GraduationCap,
  FolderOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/opportunities", label: "Opportunities", icon: Compass },
  { href: "/applications", label: "Applications", icon: FileText },
  { href: "/documents", label: "Documents", icon: FolderOpen },
  { href: "/calendar", label: "Calendar", icon: Calendar },
  { href: "/career-roadmap", label: "Career Roadmap", icon: Map },
  { href: "/agent-activity", label: "Agent Activity", icon: Bot },
  { href: "/profile", label: "Profile", icon: User },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const NavContent = () => (
    <>
      <div className="px-4 py-6 border-b border-ocean-100/60">
        <Link href="/dashboard" className="flex items-center gap-3 group" onClick={() => setMobileOpen(false)}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-ocean-600 to-ocean-800 flex items-center justify-center shadow-lg shadow-ocean-900/20 transition-transform duration-300 group-hover:scale-105">
            <GraduationCap className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="font-display text-lg font-semibold text-ocean-950 leading-tight block">
              EduPath AI
            </span>
            <span className="text-[10px] uppercase tracking-[0.2em] text-ocean-500 font-medium">
              Scholar Navigator
            </span>
          </div>
        </Link>
        <div className="mt-4">
          <Badge variant="ocean" className="normal-case tracking-normal">
            India Scholarships
          </Badge>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                active
                  ? "bg-ocean-700 text-white shadow-md shadow-ocean-900/15"
                  : "text-ocean-700 hover:bg-ocean-50 hover:text-ocean-900"
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 py-4 border-t border-ocean-100/60">
        <div className="flex items-center gap-3 mb-3 px-1">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-sand-300 to-gold-400 flex items-center justify-center text-ocean-900 text-xs font-bold">
            {user?.name?.charAt(0) || "?"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-ocean-900 truncate">{user?.name}</p>
            <p className="text-xs text-ocean-500 truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-2 px-3 py-2 rounded-xl text-sm text-ocean-600 hover:bg-red-50 hover:text-red-700 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </>
  );

  return (
    <>
      <button
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-xl bg-white/90 border border-ocean-100 shadow-md"
        onClick={() => setMobileOpen(true)}
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5 text-ocean-800" />
      </button>

      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-ocean-950/30 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={cn(
          "fixed lg:static inset-y-0 left-0 z-50 w-64 flex flex-col bg-white/90 backdrop-blur-xl border-r border-ocean-100/80",
          "transition-transform duration-300 ease-out",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        <button
          className="lg:hidden absolute top-4 right-4 p-1 rounded-lg hover:bg-ocean-50"
          onClick={() => setMobileOpen(false)}
          aria-label="Close menu"
        >
          <X className="w-5 h-5 text-ocean-600" />
        </button>
        <NavContent />
      </aside>
    </>
  );
}
