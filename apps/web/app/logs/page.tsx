'use client';

import { useEffect, useState } from 'react';
import { RefreshCw, Download } from 'lucide-react';
import { clsx } from 'clsx';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

interface LogEntry {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
  run_id?: string;
  tenant_id?: string;
}

const levelColors: Record<string, string> = {
  INFO: 'text-blue-600 dark:text-blue-400',
  WARNING: 'text-yellow-600 dark:text-yellow-400',
  ERROR: 'text-red-600 dark:text-red-400',
  DEBUG: 'text-gray-600 dark:text-gray-400',
};

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const levelParam = filter !== 'all' ? `?level=${filter}` : '';
      const res = await fetch(`${API_URL}/logs${levelParam}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLogs(data);
    } catch (err: any) {
      setError(err.message ?? 'Failed to fetch logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [filter]);

  const filteredLogs =
    filter === 'all' ? logs : logs.filter((log) => log.level === filter);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Logs</h1>
          <p className="text-muted-foreground">Platform event logs</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="input h-9 w-32"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">All Levels</option>
            <option value="INFO">Info</option>
            <option value="WARNING">Warning</option>
            <option value="ERROR">Error</option>
            <option value="DEBUG">Debug</option>
          </select>
          <button
            onClick={fetchLogs}
            className="btn-secondary h-9"
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 text-center text-red-500">
          Failed to load logs: {error}
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="max-h-[600px] overflow-y-auto font-mono text-sm">
          {filteredLogs.length === 0 && !loading ? (
            <div className="text-center py-12 text-muted-foreground">No log entries</div>
          ) : (
            filteredLogs.map((log, index) => (
              <div
                key={index}
                className="flex items-start gap-4 px-4 py-2 border-b last:border-0 hover:bg-muted/50"
              >
                <span className="text-muted-foreground whitespace-nowrap">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <span className={clsx('font-semibold w-16', levelColors[log.level])}>
                  {log.level}
                </span>
                <span className="text-muted-foreground w-24 truncate">{log.logger}</span>
                <span className="flex-1">{log.message}</span>
                {log.run_id && (
                  <span className="text-xs text-muted-foreground">{log.run_id}</span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
