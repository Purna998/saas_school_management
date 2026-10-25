import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ArrowLeft, BarChart3, BookOpen, Bus, Calendar, DollarSign, Home, MessageSquare, Package, Settings } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

// Keep unfinished modules in the shared workspace instead of sending users to a 404.
const sections = {
  fees: { title: 'Fees & Payments', description: 'A clearer picture of school fees, payments, and balances.', icon: DollarSign },
  library: { title: 'Library', description: 'A home for your books, readers, and everyday discoveries.', icon: BookOpen },
  transport: { title: 'Transport', description: 'Keep school journeys and transport arrangements together.', icon: Bus },
  hostel: { title: 'Hostel', description: 'Bring student accommodation and hostel details into one place.', icon: Home },
  inventory: { title: 'Inventory', description: 'Keep track of the resources that keep your school moving.', icon: Package },
  reports: { title: 'Reports', description: 'Turn your school information into a clearer view of progress.', icon: BarChart3 },
  communication: { title: 'Communication', description: 'Keep your school community informed and connected.', icon: MessageSquare },
  calendar: { title: 'Calendar', description: 'Make room for every class, school event, and important date.', icon: Calendar },
  settings: { title: 'School Settings', description: 'A dedicated space for your school preferences and details.', icon: Settings },
} as const;

export default async function SchoolSectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!Object.prototype.hasOwnProperty.call(sections, section)) notFound();
  const details = sections[section as keyof typeof sections];
  if (!details) notFound();

  return (
    <div className="space-y-6">
      <div><h1>{details.title}</h1><p className="text-muted-foreground">{details.description}</p></div>
      <Card className="overflow-hidden">
        <div className="h-2 bg-gradient-to-r from-[#ecdcfa] via-[#e1f3fd] to-[#fff0e6]" />
        <CardHeader className="items-center pb-3 pt-12 text-center">
          <span className="mb-4 flex size-16 items-center justify-center rounded-2xl bg-accent text-primary"><details.icon className="size-8" strokeWidth={1.5} /></span>
          <span className="mb-3 rounded-full bg-muted px-3 py-1 text-[10px] font-medium text-muted-foreground">Coming soon</span>
          <CardTitle>A little more is on the way</CardTitle>
        </CardHeader>
        <CardContent className="mx-auto max-w-md pb-12 text-center">
          <p className="text-sm leading-7 text-muted-foreground">Your {details.title.toLowerCase()} workspace is being prepared. Tools for this section are not available yet.</p>
          <Link href="/dashboard" className="mt-6 inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-xs font-medium text-primary"><ArrowLeft className="size-3.5" />Back to overview</Link>
        </CardContent>
      </Card>
    </div>
  );
}
