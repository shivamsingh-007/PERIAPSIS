'use client';

import { useState } from 'react';
import { Save, RefreshCw } from 'lucide-react';

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    defaultBudget: 10.0,
    maxIterations: 20,
    autoApprove: false,
    notificationsEnabled: true,
    logRetentionDays: 30,
    rateLimitPerMinute: 60,
  });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    // Simulate save
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setSaving(false);
  };

  return (
    <div className="space-y-6 animate-fade-in max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Configure platform settings</p>
      </div>

      <div className="card p-6 space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-4">Run Defaults</h2>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Default Budget ($)</label>
              <input
                type="number"
                className="input"
                value={settings.defaultBudget}
                onChange={(e) =>
                  setSettings({ ...settings, defaultBudget: parseFloat(e.target.value) })
                }
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Iterations</label>
              <input
                type="number"
                className="input"
                value={settings.maxIterations}
                onChange={(e) =>
                  setSettings({ ...settings, maxIterations: parseInt(e.target.value) })
                }
              />
            </div>
          </div>
        </div>

        <div className="border-t pt-6">
          <h2 className="text-lg font-semibold mb-4">Governance</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Auto-approve Low Risk</p>
                <p className="text-xs text-muted-foreground">
                  Automatically approve low-risk actions
                </p>
              </div>
              <button
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  settings.autoApprove ? 'bg-primary' : 'bg-muted'
                }`}
                onClick={() =>
                  setSettings({ ...settings, autoApprove: !settings.autoApprove })
                }
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.autoApprove ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        <div className="border-t pt-6">
          <h2 className="text-lg font-semibold mb-4">Notifications</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Enable Notifications</p>
                <p className="text-xs text-muted-foreground">
                  Receive notifications for important events
                </p>
              </div>
              <button
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  settings.notificationsEnabled ? 'bg-primary' : 'bg-muted'
                }`}
                onClick={() =>
                  setSettings({
                    ...settings,
                    notificationsEnabled: !settings.notificationsEnabled,
                  })
                }
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.notificationsEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        <div className="border-t pt-6">
          <h2 className="text-lg font-semibold mb-4">Rate Limiting</h2>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Requests per Minute</label>
              <input
                type="number"
                className="input"
                value={settings.rateLimitPerMinute}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    rateLimitPerMinute: parseInt(e.target.value),
                  })
                }
              />
            </div>
          </div>
        </div>

        <div className="border-t pt-6 flex justify-end gap-3">
          <button className="btn-secondary">
            <RefreshCw className="h-4 w-4 mr-2" />
            Reset
          </button>
          <button className="btn-primary" onClick={handleSave} disabled={saving}>
            <Save className="h-4 w-4 mr-2" />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
