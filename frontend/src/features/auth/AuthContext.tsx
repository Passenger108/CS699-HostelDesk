import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { fetchMe, login as loginRequest } from '../../api/auth';
import { loadSession, saveSession, setSessionLostHandler } from '../../api/client';
import type { User } from '../../types/user';

interface AuthState {
  user: User | null;
  isLoading: boolean;
  signIn: (loginId: string, password: string) => Promise<User>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [hasSession, setHasSession] = useState(() => loadSession() !== null);

  const me = useQuery({ queryKey: ['me'], queryFn: fetchMe, enabled: hasSession, retry: false });

  const signOut = useCallback(() => {
    saveSession(null);
    setHasSession(false);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => setSessionLostHandler(signOut), [signOut]);

  const signIn = useCallback(
    async (loginId: string, password: string) => {
      const res = await loginRequest(loginId, password);
      saveSession({ accessToken: res.access_token, refreshToken: res.refresh_token });
      queryClient.setQueryData(['me'], res.user);
      setHasSession(true);
      return res.user;
    },
    [queryClient],
  );

  const value = useMemo<AuthState>(
    () => ({
      user: hasSession ? (me.data ?? null) : null,
      isLoading: hasSession && me.isPending,
      signIn,
      signOut,
    }),
    [hasSession, me.data, me.isPending, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
