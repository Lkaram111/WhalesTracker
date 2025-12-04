import { NavLink } from '@/components/NavLink';
import { useUIStore } from '@/stores/uiStore';
import { cn } from '@/lib/utils';
import { 
  LayoutDashboard, 
  Users, 
  Radio, 
  Settings, 
  Info,
  ChevronLeft,
  ChevronRight,
  Waves,
  LineChart
} from 'lucide-react';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: Users, label: 'Whales', path: '/whales' },
  { icon: Radio, label: 'Live Feed', path: '/live' },
  { icon: LineChart, label: 'Copier Backtest', path: '/backtest' },
  { icon: Settings, label: 'Settings', path: '/settings' },
  { icon: Info, label: 'About', path: '/about' },
];

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-sidebar border-r border-sidebar-border transition-all duration-300',
        sidebarCollapsed ? 'w-16' : 'w-64'
      )}
    >
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className={cn(
          'flex items-center border-b border-sidebar-border h-16 px-4',
          sidebarCollapsed ? 'justify-center' : 'justify-between'
        )}>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/20 glow-primary">
              <Waves className="h-5 w-5 text-primary" />
            </div>
            {!sidebarCollapsed && (
              <span className="text-lg font-semibold text-foreground">WhaleTracker</span>
            )}
          </div>
          {!sidebarCollapsed && (
            <button
              onClick={toggleSidebar}
              className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-sidebar-accent transition-colors"
            >
              <ChevronLeft className="h-4 w-4 text-muted-foreground" />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                'text-muted-foreground hover:text-foreground hover:bg-sidebar-accent',
                sidebarCollapsed && 'justify-center px-2'
              )}
              activeClassName="bg-sidebar-accent text-primary glow-primary"
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              {!sidebarCollapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Collapse button when collapsed */}
        {sidebarCollapsed && (
          <div className="px-3 pb-4">
            <button
              onClick={toggleSidebar}
              className="flex h-10 w-full items-center justify-center rounded-lg hover:bg-sidebar-accent transition-colors"
            >
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>
        )}

        {/* Footer */}
        {!sidebarCollapsed && (
          <div className="border-t border-sidebar-border p-4">
            <div className="rounded-lg bg-sidebar-accent/50 p-3">
              <div className="flex items-center gap-2 mb-2">
                <div className="h-2 w-2 rounded-full bg-success animate-pulse" />
                <span className="text-xs text-muted-foreground">Live tracking</span>
              </div>
              <p className="text-xs text-muted-foreground">
                1,247 whales monitored
              </p>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
