'use client';

import { useEffect, useState } from 'react';
import {
  Play,
  DollarSign,
  AlertTriangle,
  CheckCircle,
  Clock,
  TrendingUp,
} from 'lucide-react';
import { StatCard } from '@/components/StatCard';
import { ActivityChart } from '@/components/ActivityChart';
import { RecentRuns } from '@/components/RecentRuns';

interface DashboardStats {
  totalRuns: number;
  successRate: number;
  totalCost: number;
  activeRuns: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    totalRuns: 0,
    successRate: 0,
    totalCost: 0,
    activeRuns: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const response = await fetch('/api/runs?limit=100');
      const data = await response.json();
      const runs = data.runs || [];

      const totalRuns = runs.length;
      const successRuns = runs.filter(
        (r: { state: string }) => r.state === 'SUCCESS'
      ).length;
      const successRate = totalRuns > 0 ? (successRuns / totalRuns) * 100 : 0;
      const totalCost = runs.reduce(
        (sum: number, r: { total_cost: number }) => sum + (r.total_cost || 0),
        0
      );
      const activeRuns = runs.filter(
        (r: { state: string }) =>
          !['SUCCESS', 'FAIL_TOOLING', 'FAIL_INVARIANT'].includes(r.state)
      ).length;

      setStats({ totalRuns, successRate, totalCost, activeRuns });
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your agentic loop platform
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Runs"
          value={stats.totalRuns}
          icon={Play}
          change="+12% from last week"
          changeType="positive"
        />
        <StatCard
          title="Success Rate"
          value={`${stats.successRate.toFixed(1)}%`}
          icon={CheckCircle}
          change={stats.successRate >= 90 ? 'On track' : 'Needs attention'}
          changeType={stats.successRate >= 90 ? 'positive' : 'negative'}
        />
        <StatCard
          title="Total Cost"
          value={`$${stats.totalCost.toFixed(2)}`}
          icon={DollarSign}
          description="Across all runs"
        />
        <StatCard
          title="Active Runs"
          value={stats.activeRuns}
          icon={Clock}
          description="Currently executing"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Activity Overview</h2>
          <ActivityChart />
        </div>
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Recent Runs</h2>
          <RecentRuns />
        </div>
      </div>
    </div>
  );
}
