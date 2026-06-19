'use client';

import { useEffect, useState } from 'react';
import { Shield, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/Badge';
import { DataTable } from '@/components/DataTable';

interface PolicyEvent {
  id: string;
  event_id: string;
  run_id: string;
  control_domain: string;
  policy_rule: string;
  decision: string;
  created_at: string;
}

export default function GovernancePage() {
  const [events, setEvents] = useState<PolicyEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    try {
      // Demo data
      setEvents([
        {
          id: '1',
          event_id: 'evt-001',
          run_id: 'run-001',
          control_domain: 'policy_check',
          policy_rule: 'risk_tier_medium',
          decision: 'require_approval',
          created_at: new Date().toISOString(),
        },
        {
          id: '2',
          event_id: 'evt-002',
          run_id: 'run-002',
          control_domain: 'ship_gate',
          policy_rule: 'harness_scoring',
          decision: 'pass',
          created_at: new Date(Date.now() - 3600000).toISOString(),
        },
      ]);
    } catch (error) {
      console.error('Failed to fetch events:', error);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      key: 'control_domain',
      header: 'Domain',
      sortable: true,
      render: (event: PolicyEvent) => (
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
      render: (event: PolicyEvent) => {
        const variants: Record<string, 'success' | 'error' | 'warning' | 'info'> = {
          pass: 'success',
          deny: 'error',
          require_approval: 'warning',
          approved: 'success',
          rejected: 'error',
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
      render: (event: PolicyEvent) => (
        <span className="text-muted-foreground">
          {new Date(event.created_at).toLocaleString()}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold">Governance</h1>
        <p className="text-muted-foreground">Policy enforcement and audit trail</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="card p-4 flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <p className="text-2xl font-bold">142</p>
            <p className="text-sm text-muted-foreground">Approved</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center">
            <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
          </div>
          <div>
            <p className="text-2xl font-bold">8</p>
            <p className="text-sm text-muted-foreground">Pending</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <p className="text-2xl font-bold">3</p>
            <p className="text-sm text-muted-foreground">Denied</p>
          </div>
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4">Audit Trail</h2>
        <DataTable columns={columns} data={events} pageSize={10} />
      </div>
    </div>
  );
}
