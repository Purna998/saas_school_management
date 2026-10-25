'use client';

import { ReactNode, useState } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { DashboardAccessGuard } from '@/components/auth/DashboardAccessGuard';

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <DashboardAccessGuard>
      <div className="app-frame">
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-8 focus:top-8 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-white">Skip to content</a>
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <Header />
          <main id="main-content" tabIndex={-1} className="workspace-content">
            {children}
            <footer className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t pt-5 text-[11px] text-muted-foreground"><span>© 2026 Nepal SMS</span><span>Made for better school days.</span></footer>
          </main>
        </div>
      </div>
    </DashboardAccessGuard>
  );
}
