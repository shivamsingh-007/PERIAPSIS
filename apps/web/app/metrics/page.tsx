'use client';

import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { StatCard } from '@/components/StatCard';
import { TrendingUp, DollarSign, AlertTriangle, Clock, RefreshCw } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

const COLORS = ['#22c55e', '#ef4444', '#eab308', '#3b82f6'];

interface MetricsSummary {
  total_runs: number;
  avg_latency_ms: number;
  success_rate: number;
  cost_today_usd: number;
  status_distribution: { name: string; value: number }[];
  cost_by_day: { name: string; value: number }[];
}

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/runs/metrics/summary`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMetrics(data);
    } catch (err: any) {
      setError(err.message ?? 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Metrics</h1>
            <p className="text-muted-foreground">Platform performance and cost analytics</p>
          </div>
        </div>
        <div className="text-center py-12 text-muted-foreground">Loading metrics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Metrics</h1>
            <p className="text-muted-foreground">Platform performance and cost analytics</p>
          </div>
          <button onClick={fetchMetrics} className="btn-secondary h-9">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </button>
        </div>
        <div className="card p-6 text-center text-red-500">Error: {error}</div>
      </div>
    );
  }

  const totalRuns = metrics?.total_runs ?? 0;
  const avgLatency = metrics?.avg_latency_ms ?? 0;
  const successRate = metrics?.success_rate ?? 0;
  const costToday = metrics?.cost_today_usd ?? 0;
  const stateData = metrics?.status_distribution ?? [];
  const costData = metrics?.cost_by_day ?? [];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Metrics</h1>
          <p className="text-muted-foreground">Platform performance and cost analytics</p>
        </div>
        <button onClick={fetchMetrics} className="btn-secondary h-9" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Runs"
          value={totalRuns.toString()}
          icon={TrendingUp}
        />
        <StatCard
          title="Success Rate"
          value={`${(successRate * 100).toFixed(1)}%`}
          icon={TrendingUp}
        />
        <StatCard
          title="Cost Today"
          value={`$${costToday.toFixed(2)}`}
          icon={DollarSign}
        />
        <StatCard
          title="Avg Latency"
          value={`${(avgLatency / 1000).toFixed(1)}s`}
          icon={Clock}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Cost Over Time</h2>
          <div className="h-[300px]">
            {costData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={costData}>
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                    formatter={(value: number) => [`$${value.toFixed(2)}`, 'Cost']}
                  />
                  <Bar dataKey="value" fill="hsl(221, 83%, 53%)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-muted-foreground">
                No cost data yet
              </div>
            )}
          </div>
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Run States Distribution</h2>
          <div className="h-[300px] flex items-center justify-center">
            {stateData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={stateData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {stateData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-muted-foreground">No run data yet</div>
            )}
          </div>
          {stateData.length > 0 && (
            <div className="flex justify-center gap-4 mt-4">
              {stateData.map((item, index) => (
                <div key={item.name} className="flex items-center gap-2">
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  />
                  <span className="text-sm text-muted-foreground">
                    {item.name} ({item.value})
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
