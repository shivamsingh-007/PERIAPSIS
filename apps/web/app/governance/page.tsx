'use client';

import { useEffect, useState } from 'react';
import { Shield, CheckCircle, XCircle, AlertTriangle, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/Badge';
import { DataTable } from '@/components/DataTable';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface GovernanceEvent {
  id: string;
  run_id: string;
  control_domain: string;
  policy_rule: string;
  decision: string;
  created_at: string;
}

interface GovernanceSummary {
  total: number;
  approved: number;
  pending: number;
  denied: number;
  require_approval: number;
}

export default function GovernancePage() {
  const [events, setEvents] = useState<GovernanceEvent[]>([]);
  const [summary, setSummary] = useState<GovernanceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [eventsRes, summaryRes] = await Promise.all([
        fetch(`${API_URL}/governance/events?limit=100`),
        fetch(`${API_URL}/governance/summary`),
      ]);

      if (!eventsRes.ok) throw new Error(`Events: HTTP ${eventsRes.status}`);
      if (!summaryRes.ok) throw new Error(`Summary: HTTP ${summaryRes.status}`);

      setEvents(await eventsRes.json());
      setSummary(await summaryRes.json());
    } catch (err: any) {
      setError(err.message ?? 'Failed to load governance data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const columns = [
    {
      key: 'control_domain',
      header: 'Domain',
      sortable: true,
      render: (event: GovernanceEvent) => (
        <span className="font-medium">{event.control_domain}</span>
      ),
    },
    {
      key: 'policy_rule',
      header: 'Rule',
      sortable: true,
    },
    {
      key: 'decision',
      header: 'Decision',
      sortable: true,
      render: (event: GovernanceEvent) => {
        const variants: Record<string, 'success' | 'error' | 'warning' | 'info'> = {
          pass: 'success',
          approved: 'success',
          deny: 'error',
          denied: 'error',
          require_approval: 'warning',
          pending: 'warning',
        };
        return (
          <Badge variant={variants[event.decision] || 'info'}>
            {event.decision}
          </Badge>
        );
      },
    },
    {
      key: 'created_at',
      header: 'Time',
      sortable: true,
      render: (event: GovernanceEvent) => (
        <span className="text-muted-foreground">
          {new Date(event.created_at).toLocaleString()}
        </span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Governance</h1>
            <p className="text-muted-foreground">Policy enforcement and audit trail</p>
          </div>
        </div>
        <div className="text-center py-12 text-muted-foreground">Loading governance events...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Governance</h1>
            <p className="text-muted-foreground">Policy enforcement and audit trail</p>
          </div>
          <button onClick={fetchData} className="btn-secondary h-9">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </button>
        </div>
        <div className="card p-6 text-center text-red-500">Error: {error}</div>
      </div>
    );
  }

  const approved = summary?.approved ?? 0;
  const pending = summary?.pending ?? 0;
  const denied = summary?.denied ?? 0;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Governance</h1>
          <p className="text-muted-foreground">Policy enforcement and audit trail</p>
        </div>
        <button onClick={fetchData} className="btn-secondary h-9" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="card p-4 flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <p className="text-2xl font-bold">{approved}</p>
            <p className="text-sm text-muted-foreground">Approved</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center">
            <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
          </div>
          <div>
            <p className="text-2xl font-bold">{pending}</p>
            <p className="text-sm text-muted-foreground">Pending</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <p className="text-2xl font-bold">{denied}</p>
            <p className="text-sm text-muted-foreground">Denied</p>
          </div>
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4">Audit Trail ({summary?.total ?? events.length})</h2>
        <DataTable columns={columns} data={events} pageSize={10} />
      </div>
    </div>
  );
}
