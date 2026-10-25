'use client';

import { useEffect, useState } from 'react';
import { Building2, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface Tenant {
  id: string;
  name_en: string;
  emis_code?: string;
  district?: string;
  status: string;
  subscription_plan: string;
}

interface TenantList {
  tenants: Tenant[];
  total: number;
}

export default function SchoolsPage() {
  const [schools, setSchools] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  useEffect(() => {
    void apiClient.tenant.list({ limit: 100 }).then((response) => {
      if (response.success) {
        const data = response.data as TenantList;
        setSchools(data.tenants);
      } else {
        setError(response.error?.message ?? 'Could not load schools');
      }
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-primary">Platform administration</p>
        <h1 className="text-2xl font-semibold tracking-tight">Schools & Tenants</h1>
        <p className="mt-1 text-muted-foreground">Platform-wide school directory and subscription status.</p>
      </div>

      {loading && <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading schools…</div>}
      {error && <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">{error}</p>}

      {!loading && !error && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {schools.map((school) => (
            <Card key={school.id}>
              <CardHeader className="flex flex-row items-center gap-3">
                <div className="rounded-lg bg-primary/10 p-2 text-primary"><Building2 className="h-5 w-5" /></div>
                <div>
                  <CardTitle className="text-base">{school.name_en}</CardTitle>
                  <p className="text-xs text-muted-foreground">{school.emis_code || 'No EMIS code'}</p>
                </div>
              </CardHeader>
              <CardContent className="flex items-center justify-between text-sm">
                <span>{school.district || 'District not set'}</span>
                <span className="rounded-full bg-secondary px-2 py-1 capitalize">{school.subscription_plan} · {school.status}</span>
              </CardContent>
            </Card>
          ))}
          {schools.length === 0 && <p className="text-sm text-muted-foreground">No schools have been created yet.</p>}
        </div>
      )}
    </div>
  );
}
