'use client';

import { ReactNode, useEffect, useSyncExternalStore } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store/auth';

function subscribeToHydration(onStoreChange: () => void) {
  const persistApi = useAuthStore.persist;
  if (!persistApi) return () => undefined;
  const unsubscribeStart = persistApi.onHydrate(onStoreChange);
  const unsubscribeFinish = persistApi.onFinishHydration(onStoreChange);
  return () => {
    unsubscribeStart();
    unsubscribeFinish();
  };
}

function getHydrationSnapshot() {
  return useAuthStore.persist?.hasHydrated() ?? false;
}

export function DashboardAccessGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hydrated = useSyncExternalStore(subscribeToHydration, getHydrationSnapshot, () => false);

  const isPlatformRoute = pathname.startsWith('/dashboard/platform');
  const isPlatformAdmin = user?.role === 'super_admin';
  const allowed = hydrated && isAuthenticated && user && (
    (isPlatformAdmin && pathname !== '/dashboard') ||
    (!isPlatformAdmin && !isPlatformRoute)
  );

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated || !user) {
      router.replace('/auth/login');
    } else if (isPlatformAdmin && pathname === '/dashboard') {
      router.replace('/dashboard/platform');
    } else if (!isPlatformAdmin && isPlatformRoute) {
      router.replace('/dashboard');
    }
  }, [hydrated, isAuthenticated, isPlatformAdmin, isPlatformRoute, pathname, router, user]);

  if (!allowed) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">Loading your workspace…</div>;
  }

  return children;
}
