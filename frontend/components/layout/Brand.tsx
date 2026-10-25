import { GraduationCap } from 'lucide-react';
import { cn } from '@/lib/utils';

export function Brand({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <div className={cn('flex items-center gap-2.5 text-primary', className)}>
      <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
        <GraduationCap className="size-7" strokeWidth={1.8} />
      </span>
      {!compact && <span className="whitespace-nowrap text-xl font-bold tracking-tight">Nepal<span className="font-normal"> SMS</span></span>}
    </div>
  );
}
