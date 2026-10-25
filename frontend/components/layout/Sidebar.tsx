'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronLeft, ChevronRight, GraduationCap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/lib/store/auth';
import { Brand } from './Brand';
import { getNavigation, isNavigationActive } from './navigation';

export function SidebarNavigation({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  const user = useAuthStore((state) => state.user);
  const items = getNavigation(user);

  return (
    <nav aria-label="Main navigation" className="flex-1 space-y-1 overflow-y-auto px-4 pb-4 [scrollbar-width:thin]">
      {items.map((item, index) => {
        const active = isNavigationActive(pathname, item.href);
        const newGroup = index === 0 || items[index - 1].group !== item.group;
        return (
          <div key={item.href}>
            {newGroup && !collapsed && <p className="px-3 pb-3 pt-6 text-[10px] font-semibold uppercase tracking-[.16em] text-muted-foreground/80">{item.group}</p>}
            {newGroup && collapsed && index > 0 && <div className="mx-3 my-4 border-t" />}
            <Link href={item.href} onClick={onNavigate} aria-current={active ? 'page' : undefined} title={collapsed ? item.label : undefined}
              className={cn('relative flex min-h-11 items-center gap-3 rounded-lg px-3 py-3 text-[13px] transition-colors', active ? 'bg-accent font-medium text-primary before:absolute before:-left-4 before:top-3 before:h-5 before:w-[3px] before:rounded-full before:bg-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground', collapsed && 'justify-center px-0')}>
              <item.icon className="size-[19px] shrink-0" strokeWidth={1.65} />
              {!collapsed && <span>{item.label}</span>}
              {active && !collapsed && <span className="ml-auto size-1.5 rounded-full bg-primary" />}
            </Link>
          </div>
        );
      })}
    </nav>
  );
}

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const user = useAuthStore((state) => state.user);
  return (
    <aside className="app-sidebar" data-collapsed={collapsed}>
      <div className={cn('flex h-[82px] shrink-0 items-center px-6', collapsed && 'justify-center px-0')}>
        <Link href={user?.role === 'super_admin' ? '/dashboard/platform' : '/dashboard'} aria-label="Nepal SMS home"><Brand compact={collapsed} /></Link>
      </div>
      <SidebarNavigation collapsed={collapsed} />
      {!collapsed && <div className="mx-5 mb-4 rounded-xl bg-[#faf6fd] p-4"><GraduationCap className="mb-2 size-5 text-primary" /><p className="text-xs font-medium">A little more organized.</p><p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">More time for what matters.</p></div>}
      <button onClick={onToggle} className="flex h-12 shrink-0 items-center justify-center gap-2 border-t text-xs text-muted-foreground hover:bg-muted" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed}>
        {collapsed ? <ChevronRight className="size-4" /> : <><ChevronLeft className="size-4" /><span>Collapse menu</span></>}
      </button>
    </aside>
  );
}
