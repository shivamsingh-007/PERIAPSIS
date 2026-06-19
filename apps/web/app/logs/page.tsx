'use client';

import { useEffect, useState } from 'react';
import { RefreshCw, Download, Filter } from 'lucide-react';
import { clsx } from 'clsx';

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

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    try {
      // Demo data
      setLogs([
        {
          timestamp: new Date().toISOString(),
          level: 'INFO',
          logger: 'api',
          message: 'Application starting',
        },
        {
          timestamp: new Date(Date.now() - 60000).toISOString(),
          level: 'INFO',
          logger: 'runs',
          message: 'Run created',
          run_id: 'run-001',
          tenant_id: 'tenant-001',
        },
        {
          timestamp: new Date(Date.now() - 120000).toISOString(),
          level: 'WARNING',
          logger: 'policy',
          message: 'Medium risk action requires approval',
          run_id: 'run-002',
        },
        {
          timestamp: new Date(Date.now() - 180000).toISOString(),
          level: 'ERROR',
          logger: 'tool',
          message: 'Tool execution failed: API timeout',
          run_id: 'run-003',
        },
      ]);
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLoading(false);
    }
  };

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
          </select>
          <button
            onClick={fetchLogs}
            className="btn-secondary h-9"
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button className="btn-secondary h-9">
            <Download className="h-4 w-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="max-h-[600px] overflow-y-auto font-mono text-sm">
          {filteredLogs.map((log, index) => (
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
          ))}
        </div>
      </div>
    </div>
  );
}
