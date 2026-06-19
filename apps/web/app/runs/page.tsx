'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { DataTable } from '@/components/DataTable';
import { Badge } from '@/components/Badge';
import { Plus, RefreshCw } from 'lucide-react';

interface Run {
  id: string;
  run_id: string;
  goal: string;
  state: string;
  total_cost: number;
  total_steps: number;
  created_at: string;
}

const stateColors: Record<string, 'success' | 'error' | 'warning' | 'info'> = {
  SUCCESS: 'success',
  FAIL_TOOLING: 'error',
  FAIL_INVARIANT: 'error',
  STOP_BUDGET: 'warning',
  STOP_NO_PROGRESS: 'warning',
  ESCALATED_TO_HUMAN: 'info',
};

export default function RunsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/runs?limit=100');
      const data = await response.json();
      setRuns(
        (data.runs || []).map((r: Run) => ({
          ...r,
          id: r.run_id,
        }))
      );
    } catch (error) {
      console.error('Failed to fetch runs:', error);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      key: 'goal',
      header: 'Goal',
      sortable: true,
      render: (run: Run) => (
        <span className="font-medium truncate max-w-xs block">{run.goal}</span>
      ),
    },
    {
      key: 'state',
      header: 'State',
      sortable: true,
      render: (run: Run) => (
        <Badge variant={stateColors[run.state] || 'info'}>{run.state}</Badge>
      ),
    },
    {
      key: 'total_cost',
      header: 'Cost',
      sortable: true,
      render: (run: Run) => (
        <span className="font-mono text-sm">${run.total_cost?.toFixed(4) || '0.00'}</span>
      ),
    },
    {
      key: 'total_steps',
      header: 'Steps',
      sortable: true,
      render: (run: Run) => <span>{run.total_steps || 0}</span>,
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (run: Run) => (
        <span className="text-muted-foreground">
          {new Date(run.created_at).toLocaleString()}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Runs</h1>
          <p className="text-muted-foreground">View and manage all agent runs</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchRuns}
            className="btn-secondary h-9"
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button className="btn-primary h-9">
            <Plus className="h-4 w-4 mr-2" />
            New Run
          </button>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={runs}
        pageSize={15}
        onRowClick={(run) => router.push(`/runs/${run.run_id}`)}
      />
    </div>
  );
}
