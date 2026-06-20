'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, RefreshCw, Circle } from 'lucide-react';
import { clsx } from 'clsx';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface HealthStatus {
  status: string;
  database: string;
  timestamp: number;
  langfuse?: boolean;
  redis?: boolean;
  supabase?: boolean;
}

export default function HealthPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/health`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setHealth(data);
    } catch (err: any) {
      setError(err.message ?? 'Failed to fetch health');
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const getStatusIcon = (ok: boolean) =>
    ok ? (
      <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
    ) : (
      <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
    );

  const getStatusBg = (ok: boolean) =>
    ok ? 'bg-green-100 dark:bg-green-900/30' : 'bg-red-100 dark:bg-red-900/30';

  const getStatusText = (ok: boolean) =>
    ok ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';

  const services = [
    {
      name: 'API Server',
      healthy: health?.status === 'ok',
    },
    {
      name: 'PostgreSQL',
      healthy: health?.database === 'connected',
    },
    {
      name: 'Redis',
      healthy: health?.redis ?? true,
    },
    {
      name: 'Langfuse',
      healthy: health?.langfuse ?? false,
    },
    {
      name: 'Supabase',
      healthy: health?.supabase ?? false,
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Health</h1>
          <p className="text-muted-foreground">System health status</p>
        </div>
        <button onClick={fetchHealth} className="btn-secondary h-9" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="card p-4 text-center text-red-500">
          Failed to load health: {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {services.map((service) => (
          <div key={service.name} className="card p-4 flex items-center gap-4">
            <div
              className={clsx(
                'h-10 w-10 rounded-lg flex items-center justify-center',
                getStatusBg(service.healthy)
              )}
            >
              {getStatusIcon(service.healthy)}
            </div>
            <div>
              <p className="font-medium">{service.name}</p>
              <p className={clsx('text-sm', getStatusText(service.healthy))}>
                {service.healthy ? 'Healthy' : 'Unhealthy'}
              </p>
            </div>
          </div>
        ))}
      </div>

      {health && (
        <div className="card p-4">
          <h2 className="font-medium mb-2">Last Check</h2>
          <p className="text-sm text-muted-foreground">
            {new Date(health.timestamp * 1000).toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}
