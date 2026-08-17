"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import {
  AUTH_EXPIRED_EVENT,
  SESSION_TOKEN_KEY,
  authApi,
  sessionToken,
  type AuthUser,
  type ProfileInput,
  type RegistrationInput,
} from "@/lib/auth";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegistrationInput) => Promise<void>;
  updateProfile: (input: ProfileInput) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const expire = () => {
      if (active) setUser(null);
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, expire);

    async function hydrate() {
      if (!sessionToken()) {
        if (active) setLoading(false);
        return;
      }
      try {
        const current = await authApi.me();
        if (active) setUser(current);
      } catch {
        window.localStorage.removeItem(SESSION_TOKEN_KEY);
        if (active) setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    }
    void hydrate();
    return () => {
      active = false;
      window.removeEventListener(AUTH_EXPIRED_EVENT, expire);
    };
  }, []);

  async function login(email: string, password: string) {
    const token = await authApi.login(email, password);
    window.localStorage.setItem(SESSION_TOKEN_KEY, token.access_token);
    try {
      setUser(await authApi.me());
    } catch (error) {
      window.localStorage.removeItem(SESSION_TOKEN_KEY);
      throw error;
    }
  }

  async function register(input: RegistrationInput) {
    await authApi.register(input);
    await login(input.email, input.password);
  }

  async function updateProfile(input: ProfileInput) {
    const profile = await authApi.updateProfile(input);
    setUser((current) => (current ? { ...current, profile } : current));
  }

  function logout() {
    window.localStorage.removeItem(SESSION_TOKEN_KEY);
    setUser(null);
  }

  const value = useMemo(
    () => ({ user, loading, login, register, updateProfile, logout }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
