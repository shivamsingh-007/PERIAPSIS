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
import { TrendingUp, DollarSign, AlertTriangle, Clock } from 'lucide-react';

const COLORS = ['#22c55e', '#ef4444', '#eab308', '#3b82f6'];

interface MetricData {
  name: string;
  value: number;
}

export default function MetricsPage() {
  const [costData, setCostData] = useState<MetricData[]>([]);
  const [stateData, setStateData] = useState<MetricData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMetrics();
  }, []);

  const fetchMetrics = async () => {
    try {
      // Simulated data for demo
      setCostData([
        { name: 'Mon', value: 12.5 },
        { name: 'Tue', value: 18.2 },
        { name: 'Wed', value: 15.8 },
        { name: 'Thu', value: 22.1 },
        { name: 'Fri', value: 19.4 },
        { name: 'Sat', value: 8.6 },
        { name: 'Sun', value: 5.2 },
      ]);

      setStateData([
        { name: 'Success', value: 85 },
        { name: 'Failed', value: 8 },
        { name: 'Stopped', value: 5 },
        { name: 'Escalated', value: 2 },
      ]);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold">Metrics</h1>
        <p className="text-muted-foreground">Platform performance and cost analytics</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Avg Cost/Run"
          value="$0.42"
          icon={DollarSign}
          change="-5% from last week"
          changeType="positive"
        />
        <StatCard
          title="Success Rate"
          value="92.3%"
          icon={TrendingUp}
          change="+2.1% from last week"
          changeType="positive"
        />
        <StatCard
          title="Error Rate"
          value="4.2%"
          icon={AlertTriangle}
          change="+0.3% from last week"
          changeType="negative"
        />
        <StatCard
          title="Avg Duration"
          value="2.4s"
          icon={Clock}
          change="-0.2s from last week"
          changeType="positive"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Cost Over Time</h2>
          <div className="h-[300px]">
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
          </div>
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Run States Distribution</h2>
          <div className="h-[300px] flex items-center justify-center">
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
          </div>
          <div className="flex justify-center gap-4 mt-4">
            {stateData.map((item, index) => (
              <div key={item.name} className="flex items-center gap-2">
                <div
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: COLORS[index] }}
                />
                <span className="text-sm text-muted-foreground">{item.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
