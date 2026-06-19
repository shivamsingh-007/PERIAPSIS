'use client';

import { useEffect, useState } from 'react';
import { Plus, Trash2, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/Badge';

interface Webhook {
  webhook_id: string;
  url: string;
  events: string[];
  active: boolean;
  created_at: string;
}

export default function WebhooksPage() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWebhooks();
  }, []);

  const fetchWebhooks = async () => {
    try {
      // Demo data
      setWebhooks([
        {
          webhook_id: 'wh-001',
          url: 'https://api.example.com/webhooks/runs',
          events: ['run.completed', 'run.failed'],
          active: true,
          created_at: new Date().toISOString(),
        },
        {
          webhook_id: 'wh-002',
          url: 'https://slack.example.com/webhook',
          events: ['approval.needed'],
          active: true,
          created_at: new Date(Date.now() - 86400000).toISOString(),
        },
      ]);
    } catch (error) {
      console.error('Failed to fetch webhooks:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Webhooks</h1>
          <p className="text-muted-foreground">Configure event notifications</p>
        </div>
        <button className="btn-primary h-9">
          <Plus className="h-4 w-4 mr-2" />
          Add Webhook
        </button>
      </div>

      <div className="space-y-4">
        {webhooks.map((webhook) => (
          <div key={webhook.webhook_id} className="card p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm truncate">{webhook.url}</span>
                  <ExternalLink className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant={webhook.active ? 'success' : 'default'}>
                    {webhook.active ? 'Active' : 'Inactive'}
                  </Badge>
                  {webhook.events.map((event) => (
                    <Badge key={event} variant="info">
                      {event}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Created {new Date(webhook.created_at).toLocaleDateString()}
                </p>
              </div>
              <button className="btn-ghost h-8 w-8 p-0 text-muted-foreground hover:text-destructive">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}

        {webhooks.length === 0 && !loading && (
          <div className="card p-8 text-center text-muted-foreground">
            No webhooks configured. Add one to receive event notifications.
          </div>
        )}
      </div>
    </div>
  );
}
