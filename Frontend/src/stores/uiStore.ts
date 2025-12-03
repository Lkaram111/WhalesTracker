import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  theme: 'dark' | 'light' | 'system';
  sidebarCollapsed: boolean;
  liveFeedPaused: boolean;
  setTheme: (theme: 'dark' | 'light' | 'system') => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setLiveFeedPaused: (paused: boolean) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme: 'dark',
      sidebarCollapsed: false,
      liveFeedPaused: false,
      setTheme: (theme) => set({ theme }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setLiveFeedPaused: (paused) => set({ liveFeedPaused: paused }),
    }),
    {
      name: 'whale-tracker-ui',
    }
  )
);
