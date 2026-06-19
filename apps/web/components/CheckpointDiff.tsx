'use client';

import { useState, useEffect } from 'react';

interface CheckpointDiffProps {
  runId: string;
  checkpointA: string;
  checkpointB: string;
}

interface DiffLine {
  type: 'added' | 'removed' | 'unchanged';
  content: string;
  lineNum: number;
}

interface DiffStats {
  additions: number;
  deletions: number;
  unchanged: number;
}

export default function CheckpointDiff({ runId, checkpointA, checkpointB }: CheckpointDiffProps) {
  const [diff, setDiff] = useState<DiffLine[]>([]);
  const [stats, setStats] = useState<DiffStats>({ additions: 0, deletions: 0, unchanged: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDiff();
  }, [runId, checkpointA, checkpointB]);

  async function fetchDiff() {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/runs/${runId}/checkpoints/diff?from=${checkpointA}&to=${checkpointB}`
      );
      if (!response.ok) throw new Error('Failed to fetch diff');
      const data = await response.json();

      const lines = parseDiff(data.diff);
      setDiff(lines);
      setStats({
        additions: lines.filter(l => l.type === 'added').length,
        deletions: lines.filter(l => l.type === 'removed').length,
        unchanged: lines.filter(l => l.type === 'unchanged').length,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  function parseDiff(diffText: string): DiffLine[] {
    return diffText.split('\n').map((line, i) => {
      if (line.startsWith('+')) {
        return { type: 'added', content: line.slice(1), lineNum: i + 1 };
      } else if (line.startsWith('-')) {
        return { type: 'removed', content: line.slice(1), lineNum: i + 1 };
      }
      return { type: 'unchanged', content: line, lineNum: i + 1 };
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="px-4 py-3 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">Checkpoint Diff</h3>
        <div className="flex gap-4 mt-2 text-sm">
          <span className="text-green-600">+{stats.additions} added</span>
          <span className="text-red-600">-{stats.deletions} removed</span>
          <span className="text-gray-500">{stats.unchanged} unchanged</span>
        </div>
      </div>
      <div className="overflow-auto max-h-96 font-mono text-sm">
        <table className="w-full">
          <tbody>
            {diff.map((line, i) => (
              <tr
                key={i}
                className={
                  line.type === 'added'
                    ? 'bg-green-50'
                    : line.type === 'removed'
                    ? 'bg-red-50'
                    : ''
                }
              >
                <td className="px-2 py-0.5 text-gray-400 text-right w-12 select-none">
                  {line.lineNum}
                </td>
                <td className="px-2 py-0.5">
                  <span
                    className={
                      line.type === 'added'
                        ? 'text-green-700'
                        : line.type === 'removed'
                        ? 'text-red-700'
                        : 'text-gray-700'
                    }
                  >
                    {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
                    {line.content}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
