'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { clsx } from 'clsx';
import { ExternalLink } from 'lucide-react';

interface Run {
  run_id: string;
  goal: string;
  state: string;
  total_cost: number;
  created_at: string;
}

const stateColors: Record<string, string> = {
  SUCCESS: 'badge-success',
  FAIL_TOOLING: 'badge-error',
  FAIL_INVARIANT: 'badge-error',
  STOP_BUDGET: 'badge-warning',
  STOP_NO_PROGRESS: 'badge-warning',
  ESCALATED_TO_HUMAN: 'badge-info',
};

export function RecentRuns() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    try {
      const response = await fetch('/api/runs?limit=5');
      const data = await response.json();
      setRuns(data.runs || []);
    } catch (error) {
      console.error('Failed to fetch runs:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 bg-muted animate-pulse rounded" />
        ))}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No runs yet. Create your first run to get started.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {runs.map((run) => (
        <Link
          key={run.run_id}
          href={`/runs/${run.run_id}`}
          className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors group"
        >
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{run.goal}</p>
            <p className="text-xs text-muted-foreground mt-1">
              ${run.total_cost?.toFixed(4) || '0.00'} ·{' '}
              {new Date(run.created_at).toLocaleDateString()}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className={clsx('text-xs', stateColors[run.state] || 'badge')}>
              {run.state}
            </span>
            <ExternalLink className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </Link>
      ))}
    </div>
  );
}
