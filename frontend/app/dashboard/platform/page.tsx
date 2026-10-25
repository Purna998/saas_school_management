'use client';

import Link from 'next/link';
import { Activity, ArrowRight, Building2, CreditCard, Headphones, Network, ServerCog, ShieldCheck } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/lib/store/auth';

const platformAreas = [
  { href: '/dashboard/platform/schools', title: 'Schools & Tenants', description: 'Your school community, connected. Browse schools and their subscription status.', icon: Building2, tone: 'purple', caption: 'Your school network' },
  { href: '/dashboard/platform/subscriptions', title: 'Subscriptions & Billing', description: 'A dedicated space for plans, renewals, usage limits, and billing.', icon: CreditCard, tone: 'blue', caption: 'Plans & renewals' },
  { href: '/dashboard/platform/monitoring', title: 'Monitoring', description: 'Keep your platform services and operational health in view.', icon: Activity, tone: 'peach', caption: 'Platform wellbeing' },
  { href: '/dashboard/platform/support', title: 'Support', description: 'A central place to assist your schools and their teams.', icon: Headphones, tone: 'green', caption: 'Here for your schools' },
];

export default function PlatformDashboardPage() {
  const user = useAuthStore((state) => state.user);
  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border/50 bg-white p-5 sm:p-6">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3"><div><h1>Platform Overview</h1><p className="mt-1.5 text-[13px] text-muted-foreground">Welcome back{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}. Your school network starts here.</p></div><span className="flex items-center gap-1.5 rounded-full bg-accent px-3 py-1.5 text-[10px] text-primary"><ShieldCheck className="size-3.5" />Platform administration</span></div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{platformAreas.map((area) => <Link key={area.href} href={area.href} className="stat-tile group" data-tone={area.tone}><div className="flex items-center justify-between"><area.icon className="stat-icon size-7" strokeWidth={1.6} /><ArrowRight className="size-4 text-foreground/30 transition-transform group-hover:translate-x-1" /></div><p className="mt-5 text-[13px] font-semibold">{area.title}</p><p className="mt-1.5 text-[11px] text-foreground/50">{area.caption}</p></Link>)}</div>
      </section>
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Card><CardHeader><CardTitle>Your administration workspace</CardTitle><p className="text-xs text-muted-foreground">Everything you need to look after your school network.</p></CardHeader><CardContent className="space-y-1">{platformAreas.map((area) => <Link key={area.href} href={area.href} className="group flex items-center gap-4 rounded-xl px-2 py-4 transition-colors hover:bg-muted"><span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent text-primary"><area.icon className="size-5" strokeWidth={1.6} /></span><div><h2 className="text-[13px] font-medium">{area.title}</h2><p className="mt-1 text-xs leading-5 text-muted-foreground">{area.description}</p></div><ArrowRight className="ml-auto size-4 shrink-0 text-muted-foreground group-hover:text-primary" /></Link>)}</CardContent></Card>
        <div className="space-y-6"><Card className="overflow-hidden"><CardHeader><span className="mb-3 flex size-12 items-center justify-center rounded-2xl bg-[#e8f6fd] text-[#58afd4]"><ServerCog className="size-6" strokeWidth={1.6} /></span><CardTitle>Make the platform your own</CardTitle><p className="pt-1 text-xs leading-6 text-muted-foreground">A dedicated home for global preferences, integrations, and school defaults.</p></CardHeader><CardContent><Link href="/dashboard/platform/configuration" className="inline-flex items-center gap-2 text-xs font-medium text-primary">Platform configuration<ArrowRight className="size-3.5" /></Link></CardContent></Card><Card className="bg-[#faf6fe]"><CardHeader><Network className="mb-2 size-6 text-primary" strokeWidth={1.5} /><CardTitle>One connected community</CardTitle></CardHeader><CardContent className="text-xs leading-6 text-muted-foreground">Support the bigger picture from here. Each school has its own workspace for its people, classes, and everyday activities.</CardContent></Card></div>
      </div>
    </div>
  );
}
