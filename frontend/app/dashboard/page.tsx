'use client';

import Link from 'next/link';
import { ArrowDownRight, ArrowRight, ArrowUpRight, BookOpen, ClipboardCheck, DollarSign, GraduationCap, Users, UserCog } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/lib/store/auth';
import { getNavigation, roleLabel } from '@/components/layout/navigation';
import { AttendanceTrendChart, FeeCollectionChart, StudentsByGradeChart } from './DashboardChartLoaders';

const studentsByGrade = [
  { grade: 'Nursery', count: 45 }, { grade: 'LKG', count: 52 }, { grade: 'UKG', count: 48 },
  { grade: 'Grade 1', count: 95 }, { grade: 'Grade 2', count: 88 }, { grade: 'Grade 3', count: 92 },
  { grade: 'Grade 4', count: 85 }, { grade: 'Grade 5', count: 90 }, { grade: 'Grade 6', count: 82 },
  { grade: 'Grade 7', count: 78 }, { grade: 'Grade 8', count: 75 }, { grade: 'Grade 9', count: 72 },
  { grade: 'Grade 10', count: 68 }, { grade: 'Grade 11', count: 45 }, { grade: 'Grade 12', count: 35 },
];
const attendanceTrend = [
  { month: 'Jan', attendance: 92.5 }, { month: 'Feb', attendance: 93.2 }, { month: 'Mar', attendance: 91.8 },
  { month: 'Apr', attendance: 94.1 }, { month: 'May', attendance: 93.8 }, { month: 'Jun', attendance: 94.2 },
];
const feeCollection = [{ name: 'Collected', value: 875000 }, { name: 'Pending', value: 125000 }];
const statCards = [
  { title: 'Students', value: '1,250', icon: Users, change: '12.5%', tone: 'purple', up: true },
  { title: 'Staff & Teachers', value: '85', icon: UserCog, change: '5.2%', tone: 'blue', up: true },
  { title: 'Classes', value: '45', icon: GraduationCap, change: 'Active classes', tone: 'peach' },
  { title: 'Pending Fees', value: 'NPR 125K', icon: DollarSign, change: '8.3%', tone: 'green', up: false },
];
const snapshots = [
  { label: "Today's attendance", description: 'Students present across all classes', value: '94.2%', icon: ClipboardCheck, tone: 'bg-[#e8f8ee] text-[#5abc7b]' },
  { label: 'Library books issued', description: 'Learning beyond the classroom', value: '342', icon: BookOpen, tone: 'bg-[#e7f5fd] text-[#53b3df]' },
  { label: 'New admissions', description: 'Students welcomed this month', value: '28', icon: Users, tone: 'bg-[#f2e7fc] text-[#a76ad5]' },
  { label: 'Upcoming exams', description: 'Examinations on the schedule', value: '5', icon: GraduationCap, tone: 'bg-[#fff0e6] text-[#eea06c]' },
];

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const title = user?.role === 'school_admin' ? 'Admin' : roleLabel(user?.role);
  const quickLinks = getNavigation(user).filter((item) => item.href !== '/dashboard').slice(0, 4);
  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border/50 bg-white p-5 sm:p-6">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div><h1>{title} Dashboard</h1><p className="mt-1.5 text-[13px] text-muted-foreground">Welcome back{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}. A fresh look at your school day.</p></div>
          <span className="rounded-full border bg-muted/60 px-3 py-1.5 text-[10px] text-muted-foreground" title="The overview uses sample figures. Module pages show your school records.">Demo overview</span>
        </div>
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 xl:gap-5">
          {statCards.map((stat) => <div key={stat.title} className="stat-tile" data-tone={stat.tone}>
            <div className="flex items-center justify-between gap-2"><div><p className="text-xs text-foreground/55 sm:text-[13px]">{stat.title}</p><p className="mt-2 whitespace-nowrap text-[24px] font-semibold leading-none tracking-tight sm:text-[28px]">{stat.value}</p></div><stat.icon className="stat-icon hidden size-9 shrink-0 sm:block" strokeWidth={1.65} /></div>
            <div className="mt-4 flex items-center gap-1 text-[10px] text-foreground/50">{stat.up !== undefined && (stat.up ? <ArrowUpRight className="size-3 text-[#66a878]" /> : <ArrowDownRight className="size-3 text-[#66a878]" />)}<span>{stat.change}</span>{stat.up !== undefined && <span className="hidden sm:inline">vs. last month</span>}</div>
          </div>)}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.65fr_1fr]">
        <Card><CardHeader className="flex-row items-start justify-between gap-3"><div><CardTitle>Students by Grade</CardTitle><p className="mt-1 text-xs text-muted-foreground">Student enrollment across all grades</p></div><span className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground"><span className="size-2 rounded-full bg-primary" />Students</span></CardHeader><CardContent className="px-3 pb-4 sm:px-5"><StudentsByGradeChart data={studentsByGrade} /></CardContent></Card>
        <Card><CardHeader><CardTitle>Fee Collection</CardTitle><p className="text-xs text-muted-foreground">Collected and outstanding fees</p></CardHeader><CardContent><FeeCollectionChart data={feeCollection} /><div className="mt-1 flex justify-center gap-6 text-xs"><span className="flex items-center gap-2"><span className="size-2.5 rounded-full bg-primary" />Collected</span><span className="flex items-center gap-2"><span className="size-2.5 rounded-full bg-[#ffa365]" />Pending</span></div><div className="mt-5 grid grid-cols-2 divide-x border-t pt-4 text-center"><div><p className="text-[10px] text-muted-foreground">Collected</p><p className="mt-1 text-sm font-semibold">NPR 875,000</p></div><div><p className="text-[10px] text-muted-foreground">Pending</p><p className="mt-1 text-sm font-semibold">NPR 125,000</p></div></div></CardContent></Card>
        <Card><CardHeader className="flex-row items-start justify-between gap-3"><div><CardTitle>Attendance Overview</CardTitle><p className="mt-1 text-xs text-muted-foreground">Monthly student attendance · January–June</p></div><span className="rounded-lg bg-[#edf9f0] px-2.5 py-1 text-[10px] font-medium text-[#5a9c6b]">94.2% this month</span></CardHeader><CardContent className="px-3 pb-4 sm:px-5"><AttendanceTrendChart data={attendanceTrend} /></CardContent></Card>
        <Card><CardHeader><CardTitle>School at a Glance</CardTitle><p className="text-xs text-muted-foreground">The numbers behind your school day</p></CardHeader><CardContent className="space-y-1">{snapshots.map((item) => <div key={item.label} className="flex items-center gap-3 border-b py-3.5 first:pt-0 last:border-0"><span className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${item.tone}`}><item.icon className="size-5" strokeWidth={1.6} /></span><div className="min-w-0"><p className="text-xs font-medium">{item.label}</p><p className="mt-1 text-[10px] leading-4 text-muted-foreground">{item.description}</p></div><span className="ml-auto text-lg font-semibold tracking-tight">{item.value}</span></div>)}</CardContent></Card>
      </div>
      {quickLinks.length > 0 && <Card><CardHeader className="pb-4"><CardTitle>Make it a productive day</CardTitle><p className="text-xs text-muted-foreground">Your everyday essentials, a click away.</p></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{quickLinks.map((item) => <Link key={item.href} href={item.href} className="group flex items-center gap-3 rounded-xl border p-3.5 text-xs transition-colors hover:border-primary/20 hover:bg-accent"><item.icon className="size-4 text-primary" />{item.label}<ArrowRight className="ml-auto size-3.5 text-muted-foreground group-hover:text-primary" /></Link>)}</CardContent></Card>}
    </div>
  );
}
