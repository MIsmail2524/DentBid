import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { api, setAuthToken } from './api';
import { getPushToken } from './push';
import { connectRealtime } from './realtime';
import { getItem, setItem } from './storage';
import type { User } from './types';

const TOKEN_KEY = 'dentbid.token';

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: Parameters<typeof api.register>[0]) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setUser: (u: User) => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const start = useCallback(async (token: string) => {
    setAuthToken(token);
    connectRealtime(token);
    getPushToken().then((push_token) => {
      if (push_token) api.updateMe({ push_token }).catch(() => undefined);
    });
  }, []);

  useEffect(() => {
    (async () => {
      const token = await getItem(TOKEN_KEY);
      if (token) {
        setAuthToken(token);
        try {
          setUser(await api.me());
          await start(token);
        } catch {
          setAuthToken(null);
          await setItem(TOKEN_KEY, null);
        }
      }
      setLoading(false);
    })();
  }, [start]);

  // stable identity: screens call this from focus effects, so it must not change on every user update
  const refresh = useCallback(async () => setUser(await api.me()), []);

  const value = useMemo<AuthCtx>(() => ({
    user,
    loading,
    login: async (email, password) => {
      const r = await api.login(email, password);
      await setItem(TOKEN_KEY, r.access_token);
      await start(r.access_token);
      setUser(r.user);
      return r.user;
    },
    register: async (data) => {
      const r = await api.register(data);
      await setItem(TOKEN_KEY, r.access_token);
      await start(r.access_token);
      setUser(r.user);
      return r.user;
    },
    logout: async () => {
      await setItem(TOKEN_KEY, null);
      setAuthToken(null);
      connectRealtime(null);
      setUser(null);
    },
    refresh,
    setUser,
  }), [user, loading, start, refresh]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useAuth must be used inside AuthProvider');
  return c;
}
