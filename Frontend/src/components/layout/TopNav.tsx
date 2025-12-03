import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Bell, Menu } from 'lucide-react';
import { useUIStore } from '@/stores/uiStore';
import { cn } from '@/lib/utils';

export function TopNav() {
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // For now, navigate to whales with search query
      navigate(`/whales?search=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <header className={cn(
      'fixed top-0 right-0 z-30 h-16 border-b border-border bg-background/80 backdrop-blur-md transition-all duration-300',
      sidebarCollapsed ? 'left-16' : 'left-64'
    )}>
      <div className="flex h-full items-center justify-between px-6">
        {/* Left section */}
        <div className="flex items-center gap-4">
          <button
            onClick={toggleSidebar}
            className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors lg:hidden"
          >
            <Menu className="h-5 w-5 text-muted-foreground" />
          </button>
          
          {/* Search */}
          <form onSubmit={handleSearch} className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search address or label..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-10 w-64 lg:w-96 rounded-lg border border-border bg-muted/50 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            />
          </form>
        </div>

        {/* Right section */}
        <div className="flex items-center gap-3">
          {/* Live indicator */}
          <div className="hidden sm:flex items-center gap-2 rounded-full bg-success/10 px-3 py-1.5">
            <div className="h-2 w-2 rounded-full bg-success animate-pulse" />
            <span className="text-xs font-medium text-success">Live</span>
          </div>

          {/* Notifications */}
          <button className="relative flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors">
            <Bell className="h-5 w-5 text-muted-foreground" />
            <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-destructive" />
          </button>
        </div>
      </div>
    </header>
  );
}
