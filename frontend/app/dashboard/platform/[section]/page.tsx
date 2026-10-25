import Link from 'next/link';
import { notFound } from 'next/navigation';
import { Activity, ArrowLeft, CreditCard, Headphones, ServerCog } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const sections = {
  subscriptions: {
    title: 'Subscriptions & Billing',
    description: 'Manage plans, renewals, usage limits, invoices, and billing across every school.',
    icon: CreditCard,
  },
  configuration: {
    title: 'Platform Configuration',
    description: 'Configure global services, platform policies, integrations, and tenant defaults.',
    icon: ServerCog,
  },
  monitoring: {
    title: 'Monitoring',
    description: 'Monitor service health, background jobs, infrastructure, and platform incidents.',
    icon: Activity,
  },
  support: {
    title: 'Support',
    description: 'Handle support requests and assist authorized users across all schools.',
    icon: Headphones,
  },
} as const;

export default async function PlatformSectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!Object.prototype.hasOwnProperty.call(sections, section)) notFound();
  const details = sections[section as keyof typeof sections];

  if (!details) notFound();

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-primary">Platform administration</p>
        <h1 className="text-2xl font-semibold tracking-tight">{details.title}</h1>
        <p className="mt-1 text-muted-foreground">{details.description}</p>
      </div>
      <Card className="overflow-hidden">
        <div className="h-2 bg-gradient-to-r from-[#ecdcfa] via-[#e1f3fd] to-[#fff0e6]" />
        <CardHeader className="items-center pb-3 pt-12 text-center">
          <span className="mb-4 flex size-16 items-center justify-center rounded-2xl bg-accent text-primary"><details.icon className="size-8" strokeWidth={1.5} /></span>
          <span className="mb-3 rounded-full bg-muted px-3 py-1 text-[10px] font-medium text-muted-foreground">Coming soon</span>
          <CardTitle>A little more is on the way</CardTitle>
        </CardHeader>
        <CardContent className="mx-auto max-w-md pb-12 text-center">
          <p className="text-sm leading-7 text-muted-foreground">Your {details.title.toLowerCase()} workspace is being prepared. Management tools for this section are not available yet.</p>
          <Link href="/dashboard/platform" className="mt-6 inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-xs font-medium text-primary"><ArrowLeft className="size-3.5" />Back to overview</Link>
        </CardContent>
      </Card>
    </div>
  );
}
