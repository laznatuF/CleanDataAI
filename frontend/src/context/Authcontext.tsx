// frontend/src/context/Authcontext.tsx
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  authMe,
  authRequestLogin,
  authVerifyOtp,
  authVerifyToken,
  authLogout,
  authRegister,
  authSetPlan,
  type User,
} from "../libs/api";

type AuthCtx = {
  user: User;
  loading: boolean;
  requestLogin: (email: string, name?: string) => Promise<void>;
  verifyToken: (token: string) => Promise<void>;
  verifyOtp: (email: string, code: string) => Promise<void>;
  register: (email: string, name: string, plan: string) => Promise<void>;
  setPlan: (plan: string) => Promise<void>;
  logout: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const m = await authMe();
        setUser(m.user);
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const api = useMemo<AuthCtx>(
    () => ({
      user,
      loading,

      async requestLogin(email, name = "") {
        await authRequestLogin(email, name);
      },

      async verifyToken(token: string) {
        const res = await authVerifyToken(token);
        setUser(res.user);
      },

      async verifyOtp(email: string, code: string) {
        const res = await authVerifyOtp(email, code);
        setUser(res.user);
      },

      async register(email: string, name: string, plan: string) {
        const res = await authRegister({ email, name, plan });
        setUser(res.user);
      },

      async setPlan(plan: string) {
        const res = await authSetPlan(plan);
        setUser(res.user);
      },

      async logout() {
        await authLogout();
        setUser(null);
      },
    }),
    [user, loading]
  );

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return v;
}
