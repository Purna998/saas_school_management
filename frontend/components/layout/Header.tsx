'use client';

import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Bell, ChevronDown, ChevronRight, LogOut, Menu, Search, ShieldCheck, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store/auth';
import { apiClient } from '@/lib/api/client';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Brand } from './Brand';
import { SidebarNavigation } from './Sidebar';
import { getNavigation, roleLabel } from './navigation';

export function Header() {
  const { user, clearAuth } = useAuthStore();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const results = getNavigation(user).filter((item) => item.label.toLowerCase().includes(search.toLowerCase()));
  const initials = (user?.full_name || 'User').split(' ').filter(Boolean).slice(0, 2).map((part) => part[0]).join('');

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        setSearchOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  const handleLogout = async () => {
    setLoggingOut(true);
    try { await apiClient.auth.logout(); }
    catch (error) { console.error('Logout error:', error); }
    finally { queryClient.clear(); clearAuth(); router.push('/auth/login'); }
  };

  return (
    <>
      <header className="app-header">
        <div className="flex min-w-0 items-center gap-2">
          <button className="icon-button lg:hidden" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu className="size-5" /></button>
          <button onClick={() => { setSearch(''); setSearchOpen(true); }} className="flex h-11 items-center gap-3 rounded-xl bg-[#fcf9fe] px-3.5 text-left text-[12px] text-muted-foreground transition-colors hover:bg-accent sm:w-64 xl:w-80" aria-label="Search workspace">
            <span className="hidden flex-1 sm:block">What do you want to find?</span>
            <Search className="size-[18px] text-primary" strokeWidth={1.7} />
            <kbd className="hidden rounded border bg-white px-1.5 py-0.5 text-[10px] text-muted-foreground xl:block">Ctrl K</kbd>
          </button>
          <span className="truncate text-sm font-semibold text-primary sm:hidden">Nepal SMS</span>
        </div>
        <div className="flex shrink-0 items-center gap-2 sm:gap-4">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild><button className="icon-button bg-muted/70" aria-label="Notifications"><Bell className="size-[19px]" strokeWidth={1.7} /></button></DropdownMenu.Trigger>
            <DropdownMenu.Portal><DropdownMenu.Content sideOffset={12} align="end" className="z-50 w-72 rounded-2xl border bg-white p-5 shadow-xl shadow-purple-950/5"><p className="text-sm font-semibold">Notifications</p><div className="py-6 text-center"><Bell className="mx-auto mb-3 size-7 text-primary/50" /><p className="text-sm font-medium">A little peace and quiet</p><p className="mt-2 text-xs leading-relaxed text-muted-foreground">No notifications are available in this workspace yet.</p></div></DropdownMenu.Content></DropdownMenu.Portal>
          </DropdownMenu.Root>
          <div className="hidden h-7 border-l sm:block" />
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className="flex items-center gap-3 rounded-xl py-1 text-left focus-visible:outline-primary" aria-label="Account menu">
                <span className="flex size-10 items-center justify-center rounded-full bg-[#ebdef7] text-sm font-semibold text-primary">{initials}</span>
                <span className="hidden max-w-40 sm:block"><span className="block truncate text-[13px] font-medium">{user?.full_name || 'User'}</span><span className="mt-0.5 block text-[11px] text-muted-foreground">{roleLabel(user?.role)}</span></span>
                <ChevronDown className="hidden size-4 text-muted-foreground sm:block" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal><DropdownMenu.Content sideOffset={14} align="end" className="z-50 w-64 rounded-xl border bg-white p-2 shadow-xl shadow-purple-950/5">
              <div className="px-3 py-3"><p className="text-sm font-medium">{user?.full_name}</p><p className="mt-1 truncate text-xs text-muted-foreground">{user?.email}</p><p className="mt-2 flex items-center gap-1.5 text-xs text-primary"><ShieldCheck className="size-3.5" />{roleLabel(user?.role)}</p></div>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item disabled={loggingOut} onSelect={() => void handleLogout()} className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-destructive outline-none focus:bg-destructive/5 data-[disabled]:opacity-50"><LogOut className="size-4" />{loggingOut ? 'Signing out…' : 'Sign out'}</DropdownMenu.Item>
            </DropdownMenu.Content></DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </header>

      <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
        <DialogContent className="max-w-lg p-0">
          <DialogHeader className="mb-0 border-b px-5 pb-4 pt-5"><DialogTitle>Find your way</DialogTitle><DialogDescription>Search the sections in your workspace.</DialogDescription></DialogHeader>
          <div className="px-5 pt-4"><Input autoFocus placeholder="Search students, attendance, exams…" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Search sections" /></div>
          <div className="max-h-80 space-y-1 overflow-y-auto p-3">
            {results.map((item) => <Link key={item.href} href={item.href} onClick={() => setSearchOpen(false)} className="flex items-center gap-3 rounded-lg px-3 py-3 text-sm hover:bg-accent focus-visible:bg-accent"><item.icon className="size-4 text-primary" />{item.label}<ChevronRight className="ml-auto size-4 text-muted-foreground" /></Link>)}
            {!results.length && <p className="px-3 py-8 text-center text-sm text-muted-foreground">No sections found. Try another search.</p>}
          </div>
        </DialogContent>
      </Dialog>

      <DialogPrimitive.Root open={mobileOpen} onOpenChange={setMobileOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[#2d1645]/30 backdrop-blur-sm" />
          <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col bg-white shadow-xl">
            <div className="flex h-20 shrink-0 items-center justify-between px-5"><Brand /><DialogPrimitive.Close className="icon-button" aria-label="Close navigation"><X className="size-5" /></DialogPrimitive.Close></div>
            <DialogPrimitive.Title className="sr-only">Workspace navigation</DialogPrimitive.Title>
            <DialogPrimitive.Description className="sr-only">Choose a section of your school workspace.</DialogPrimitive.Description>
            <SidebarNavigation onNavigate={() => setMobileOpen(false)} />
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </>
  );
}
