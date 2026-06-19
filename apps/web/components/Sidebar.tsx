'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Play,
  BarChart3,
  Settings,
  Shield,
  Bell,
  FileText,
  Activity,
} from 'lucide-react';
import { clsx } from 'clsx';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Runs', href: '/runs', icon: Play },
  { name: 'Metrics', href: '/metrics', icon: BarChart3 },
  { name: 'Governance', href: '/governance', icon: Shield },
  { name: 'Webhooks', href: '/webhooks', icon: Bell },
  { name: 'Logs', href: '/logs', icon: FileText },
  { name: 'Health', href: '/health', icon: Activity },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r bg-card flex flex-col">
      <div className="p-6 border-b">
        <h1 className="text-xl font-bold text-primary">Agentic Loop</h1>
        <p className="text-xs text-muted-foreground mt-1">Platform Admin</p>
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
            <span className="text-sm font-medium text-primary">A</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium">Admin</p>
            <p className="text-xs text-muted-foreground truncate">admin@agentic.io</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
