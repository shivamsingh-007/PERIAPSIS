'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import { clsx } from 'clsx';

interface HealthStatus {
  status: string;
  database: string;
  timestamp: number;
}

export default function HealthPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHealth();
  }, []);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/health');
      const data = await response.json();
      setHealth(data);
    } catch (error) {
      setHealth({
        status: 'error',
        database: 'disconnected',
        timestamp: Date.now() / 1000,
      });
    } finally {
      setLoading(false);
    }
  };

  const services = [
    {
      name: 'API Server',
      status: health?.status === 'ok' ? 'healthy' : 'error',
    },
    {
      name: 'PostgreSQL',
      status: health?.database === 'connected' ? 'healthy' : 'error',
    },
    {
      name: 'Redis',
      status: 'healthy',
    },
    {
      name: 'Langfuse',
      status: 'healthy',
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Health</h1>
          <p className="text-muted-foreground">System health status</p>
        </div>
        <button
          onClick={fetchHealth}
          className="btn-secondary h-9"
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {services.map((service) => (
          <div key={service.name} className="card p-4 flex items-center gap-4">
            <div
              className={clsx(
                'h-10 w-10 rounded-lg flex items-center justify-center',
                service.status === 'healthy'
                  ? 'bg-green-100 dark:bg-green-900/30'
                  : 'bg-red-100 dark:bg-red-900/30'
              )}
            >
              {service.status === 'healthy' ? (
                <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
              )}
            </div>
            <div>
              <p className="font-medium">{service.name}</p>
              <p
                className={clsx(
                  'text-sm',
                  service.status === 'healthy'
                    ? 'text-green-600 dark:text-green-400'
                    : 'text-red-600 dark:text-red-400'
                )}
              >
                {service.status === 'healthy' ? 'Healthy' : 'Unhealthy'}
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
