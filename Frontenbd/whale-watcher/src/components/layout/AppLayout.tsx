import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';
import { useUIStore } from '@/stores/uiStore';
import { cn } from '@/lib/utils';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const { sidebarCollapsed } = useUIStore();

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <TopNav />
      <main className={cn(
        'min-h-screen pt-16 transition-all duration-300',
        sidebarCollapsed ? 'pl-16' : 'pl-64'
      )}>
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
