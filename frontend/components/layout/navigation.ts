import {
  Activity, BarChart3, BookOpen, Building2, Bus, Calendar, ClipboardCheck,
  CreditCard, DollarSign, FileText, GraduationCap, Headphones, Home,
  LayoutDashboard, MessageSquare, Package, ServerCog, Settings, UserCog, Users,
} from 'lucide-react';
import type { User } from '@/lib/store/auth';

const schoolMenu = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Overview', group: 'Workspace' },
  { href: '/dashboard/students', icon: Users, label: 'Students', permission: 'student:read', group: 'Workspace' },
  { href: '/dashboard/staff', icon: UserCog, label: 'Staff & Teachers', permission: 'staff:read', group: 'Workspace' },
  { href: '/dashboard/academic', icon: GraduationCap, label: 'Academics', permission: 'academic:read', group: 'Workspace' },
  { href: '/dashboard/attendance', icon: ClipboardCheck, label: 'Attendance', permission: 'attendance:read', group: 'Workspace' },
  { href: '/dashboard/exams', icon: FileText, label: 'Exams & Results', permission: 'exam:read', group: 'Workspace' },
  { href: '/dashboard/fees', icon: DollarSign, label: 'Fees & Payments', permission: 'fee:read', group: 'Management' },
  { href: '/dashboard/library', icon: BookOpen, label: 'Library', permission: 'library:read', group: 'Management' },
  { href: '/dashboard/transport', icon: Bus, label: 'Transport', permission: 'transport:read', group: 'Management' },
  { href: '/dashboard/hostel', icon: Home, label: 'Hostel', permission: 'hostel:read', group: 'Management' },
  { href: '/dashboard/inventory', icon: Package, label: 'Inventory', permission: 'inventory:read', group: 'Management' },
  { href: '/dashboard/reports', icon: BarChart3, label: 'Reports', permission: 'report:read', group: 'Management' },
  { href: '/dashboard/communication', icon: MessageSquare, label: 'Communication', permission: 'communication:read', group: 'Management' },
  { href: '/dashboard/calendar', icon: Calendar, label: 'Calendar', permission: 'calendar:read', group: 'Management' },
  { href: '/dashboard/settings', icon: Settings, label: 'School Settings', permission: 'tenant:update', group: 'Management' },
];

const platformMenu = [
  { href: '/dashboard/platform', icon: LayoutDashboard, label: 'Platform Overview', group: 'Platform' },
  { href: '/dashboard/platform/schools', icon: Building2, label: 'Schools & Tenants', group: 'Platform' },
  { href: '/dashboard/platform/subscriptions', icon: CreditCard, label: 'Subscriptions & Billing', group: 'Platform' },
  { href: '/dashboard/platform/configuration', icon: ServerCog, label: 'Configuration', group: 'Administration' },
  { href: '/dashboard/platform/monitoring', icon: Activity, label: 'Monitoring', group: 'Administration' },
  { href: '/dashboard/platform/support', icon: Headphones, label: 'Support', group: 'Administration' },
];

export function getNavigation(user: User | null) {
  if (user?.role === 'super_admin') return platformMenu;
  const permissions = new Set(user?.permissions ?? []);
  return schoolMenu.filter((item) => !item.permission || permissions.has(item.permission));
}

export function isNavigationActive(pathname: string, href: string) {
  const overview = href === '/dashboard' || href === '/dashboard/platform';
  return pathname === href || (!overview && pathname.startsWith(`${href}/`));
}

export function roleLabel(role?: string) {
  return (role || 'School member').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
