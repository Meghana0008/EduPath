"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { api, clearToken, setDemoMode, setToken } from "./api";
import type { User } from "./types";

interface AuthContextValue {
  user: User | null;
  demoMode: boolean;
  loading: boolean;
  onboardingCompleted: boolean | null;
  requestCode: (
    email: string,
    name?: string
  ) => Promise<{
    ok: boolean;
    needs_name?: boolean;
    message?: string;
    email_sent?: boolean;
    dev_code?: string | null;
    is_new_user?: boolean;
  }>;
  verifyCode: (email: string, code: string, name?: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  refreshOnboarding: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function routeAfterAuth(router: ReturnType<typeof useRouter>) {
  try {
    const status = await api.onboardingStatus();
    if (!status.onboarding_completed) {
      router.replace("/onboarding");
    } else {
      router.replace("/dashboard");
    }
  } catch {
    router.replace("/onboarding");
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [demoMode, setDemoModeState] = useState(false);
  const [onboardingCompleted, setOnboardingCompleted] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const refreshOnboarding = useCallback(async () => {
    try {
      const status = await api.onboardingStatus();
      setOnboardingCompleted(status.onboarding_completed);
    } catch {
      setOnboardingCompleted(false);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me);
      setDemoModeState(Boolean(me.is_demo));
      setDemoMode(Boolean(me.is_demo));
      await refreshOnboarding();
    } catch {
      setUser(null);
      clearToken();
      setOnboardingCompleted(null);
    }
  }, [refreshOnboarding]);

  useEffect(() => {
    const init = async () => {
      const token = typeof window !== "undefined" ? localStorage.getItem("edupath_token") : null;
      if (token) {
        await refreshUser();
      }
      setLoading(false);
    };
    init();
  }, [refreshUser]);

  useEffect(() => {
    if (loading) return;
    const isLoginPage = pathname === "/login";
    const isOnboarding = pathname === "/onboarding";
    if (!user && !isLoginPage) {
      router.replace("/login");
      return;
    }
    if (user && isLoginPage) {
      routeAfterAuth(router);
      return;
    }
    if (user && onboardingCompleted === false && !isOnboarding) {
      router.replace("/onboarding");
      return;
    }
    if (user && onboardingCompleted === true && isOnboarding) {
      router.replace("/dashboard");
    }
  }, [user, loading, pathname, router, onboardingCompleted]);

  const requestCode = async (email: string, name?: string) => {
    return api.requestCode(email, name);
  };

  const verifyCode = async (email: string, code: string, name?: string) => {
    const res = await api.verifyCode(email, code, name);
    setToken(res.access_token);
    setDemoMode(Boolean(res.demo_mode));
    setDemoModeState(Boolean(res.demo_mode));
    const me = await api.me();
    setUser(me);
    await refreshOnboarding();
    await routeAfterAuth(router);
  };

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password);
    setToken(res.access_token);
    setDemoMode(Boolean(res.demo_mode));
    setDemoModeState(Boolean(res.demo_mode));
    const me = await api.me();
    setUser(me);
    await refreshOnboarding();
    await routeAfterAuth(router);
  };

  const register = async (name: string, email: string, password: string) => {
    const res = await api.register(name, email, password);
    setToken(res.access_token);
    setDemoMode(false);
    setDemoModeState(false);
    const me = await api.me();
    setUser(me);
    setOnboardingCompleted(false);
    router.replace("/onboarding");
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setDemoModeState(false);
    setOnboardingCompleted(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        demoMode,
        loading,
        onboardingCompleted,
        requestCode,
        verifyCode,
        login,
        register,
        logout,
        refreshUser,
        refreshOnboarding,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
