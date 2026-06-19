'use client';

import { useState, useEffect } from 'react';
import { Activity, Users, AlertTriangle, CheckCircle, Clock, Zap } from 'lucide-react';

interface FleetJob {
  job_id: string;
  goal: string;
  state: string;
  swarm_name: string;
  risk_tier: string;
  created_at: string;
  completed_at?: string;
  cost: number;
  worker_count: number;
}

interface WorkerStatus {
  worker_id: string;
  state: string;
  current_task: string;
  uptime: number;
}

interface FleetStats {
  total_jobs: number;
  active_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_cost: number;
  avg_completion_time: number;
}

export default function FleetBoard() {
  const [jobs, setJobs] = useState<FleetJob[]>([]);
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [stats, setStats] = useState<FleetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  async function fetchData() {
    try {
      const [jobsRes, workersRes, statsRes] = await Promise.all([
        fetch('/api/fleet/jobs'),
        fetch('/api/fleet/workers'),
        fetch('/api/fleet/stats'),
      ]);

      if (jobsRes.ok) {
        const jobsData = await jobsRes.json();
        setJobs(jobsData.jobs || []);
      }

      if (workersRes.ok) {
        const workersData = await workersRes.json();
        setWorkers(workersData.workers || []);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch fleet data');
    } finally {
      setLoading(false);
    }
  }

  const filteredJobs = filter === 'all' ? jobs : jobs.filter(j => j.state === filter);

  const stateColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    running: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    blocked: 'bg-gray-100 text-gray-800',
  };

  const riskColors: Record<string, string> = {
    low: 'text-green-600',
    medium: 'text-yellow-600',
    high: 'text-red-600',
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Fleet Orchestration Board</h1>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center gap-3">
                <Activity className="h-8 w-8 text-blue-600" />
                <div>
                  <p className="text-sm text-gray-500">Total Jobs</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.total_jobs}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center gap-3">
                <Clock className="h-8 w-8 text-yellow-600" />
                <div>
                  <p className="text-sm text-gray-500">Active Jobs</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.active_jobs}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="h-8 w-8 text-green-600" />
                <div>
                  <p className="text-sm text-gray-500">Completed</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.completed_jobs}</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-center gap-3">
                <Zap className="h-8 w-8 text-purple-600" />
                <div>
                  <p className="text-sm text-gray-500">Total Cost</p>
                  <p className="text-2xl font-bold text-gray-900">${stats.total_cost.toFixed(2)}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Workers */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Users className="h-5 w-5" />
              Active Workers ({workers.length})
            </h2>
          </div>
          <div className="p-4">
            {workers.length === 0 ? (
              <p className="text-gray-500">No active workers</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {workers.map(worker => (
                  <div
                    key={worker.worker_id}
                    className="border border-gray-200 rounded-lg p-3"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-gray-900">{worker.worker_id}</span>
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${
                          worker.state === 'idle'
                            ? 'bg-green-100 text-green-800'
                            : 'bg-blue-100 text-blue-800'
                        }`}
                      >
                        {worker.state}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 truncate">{worker.current_task || 'No task'}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      Uptime: {Math.floor(worker.uptime / 3600)}h {Math.floor((worker.uptime % 3600) / 60)}m
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Jobs */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Jobs</h2>
            <div className="flex gap-2">
              {['all', 'running', 'pending', 'completed', 'failed'].map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    filter === f
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Job ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Goal</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">State</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Swarm</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Risk</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cost</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredJobs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                      No jobs found
                    </td>
                  </tr>
                ) : (
                  filteredJobs.map(job => (
                    <tr key={job.job_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-mono text-gray-900">
                        {job.job_id.slice(0, 8)}...
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 max-w-xs truncate">
                        {job.goal}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-1 rounded-full text-xs font-medium ${
                            stateColors[job.state] || 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {job.state}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{job.swarm_name}</td>
                      <td className="px-4 py-3">
                        <span className={`text-sm font-medium ${riskColors[job.risk_tier] || ''}`}>
                          {job.risk_tier}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">${job.cost.toFixed(4)}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {new Date(job.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
