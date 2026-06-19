'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const data = [
  { name: 'Mon', runs: 12, success: 10, failed: 2 },
  { name: 'Tue', runs: 19, success: 17, failed: 2 },
  { name: 'Wed', runs: 15, success: 14, failed: 1 },
  { name: 'Thu', runs: 22, success: 20, failed: 2 },
  { name: 'Fri', runs: 18, success: 16, failed: 2 },
  { name: 'Sat', runs: 8, success: 7, failed: 1 },
  { name: 'Sun', runs: 5, success: 5, failed: 0 },
];

export function ActivityChart() {
  return (
    <div className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 12 }}
            tickLine={false}
          />
          <YAxis tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '8px',
            }}
          />
          <Line
            type="monotone"
            dataKey="success"
            stroke="hsl(142, 76%, 36%)"
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="failed"
            stroke="hsl(0, 84%, 60%)"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
