'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Users,
  GraduationCap,
  ClipboardCheck,
  FileText,
  DollarSign,
  UserCog,
  BookOpen,
  Bus,
  Home,
  Package,
  BarChart3,
  MessageSquare,
  Calendar,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useState } from 'react';

const menuItems = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/dashboard/students', icon: Users, label: 'Students' },
  { href: '/dashboard/staff', icon: UserCog, label: 'Staff' },
  { href: '/dashboard/academic', icon: GraduationCap, label: 'Academic' },
  { href: '/dashboard/attendance', icon: ClipboardCheck, label: 'Attendance' },
  { href: '/dashboard/exams', icon: FileText, label: 'Exams' },
  { href: '/dashboard/fees', icon: DollarSign, label: 'Fees' },
  { href: '/dashboard/library', icon: BookOpen, label: 'Library' },
  { href: '/dashboard/transport', icon: Bus, label: 'Transport' },
  { href: '/dashboard/hostel', icon: Home, label: 'Hostel' },
  { href: '/dashboard/inventory', icon: Package, label: 'Inventory' },
  { href: '/dashboard/reports', icon: BarChart3, label: 'Reports' },
  { href: '/dashboard/communication', icon: MessageSquare, label: 'Communication' },
  { href: '/dashboard/calendar', icon: Calendar, label: 'Calendar' },
  { href: '/dashboard/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen border-r bg-card transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      <div className="flex h-16 items-center justify-between border-b px-4">
        {!collapsed && (
          <div className="flex items-center space-x-2">
            <GraduationCap className="h-8 w-8 text-primary" />
            <span className="text-xl font-bold">Nepal SMS</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="rounded-lg p-2 hover:bg-accent"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      <nav className="space-y-1 p-2">
        {menuItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                collapsed && 'justify-center'
              )}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
