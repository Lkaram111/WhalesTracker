import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '@/lib/apiClient';
import type { ChainId, CopierSessionStatus, LiveTrade } from '@/types/api';

type CopierStatus = {
  processed: number;
  errors: string[];
  notifications: string[];
};

export type CopierInstance = {
  sessionId: number;
  chain: ChainId;
  address: string;
  runId: number;
  positionSizePct?: number | null;
  leverage?: number | null;
  execute: boolean;
  label?: string | null;
  active: boolean;
  createdAt: number;
  status: CopierStatus;
  feed: LiveTrade[];
  lastTimestamp?: string;
};

interface CopierState {
  copiers: Record<number, CopierInstance>;
  isPolling: boolean;
  startCopier: (params: {
    chain: ChainId;
    address: string;
    runId: number;
    positionSizePct?: number | null;
    leverage?: number | null;
    execute?: boolean;
    label?: string | null;
  }) => Promise<CopierInstance>;
  stopCopier: (sessionId: number) => Promise<void>;
  removeCopier: (sessionId: number) => void;
  restoreSessions: () => Promise<void>;
  pollActiveCopiers: () => Promise<void>;
}

const MAX_FEED = 120;

const toStatus = (payload: CopierSessionStatus): CopierStatus => ({
  processed: payload.processed,
  errors: payload.errors || [],
  notifications: payload.notifications || [],
});

const mergeTrades = (current: LiveTrade[], next: LiveTrade[]) => {
  if (!next.length) return { feed: current, last: current.length ? current[current.length - 1].timestamp : undefined };
  const seen = new Set(current.map((t) => t.id));
  const merged = [...current];
  for (const t of next) {
    if (!seen.has(t.id)) {
      merged.push(t);
      seen.add(t.id);
    }
  }
  const trimmed = merged.slice(-MAX_FEED);
  const last = next[next.length - 1]?.timestamp ?? trimmed[trimmed.length - 1]?.timestamp;
  return { feed: trimmed, last };
};

export const useCopierStore = create<CopierState>()(
  persist(
    (set, get) => ({
      copiers: {},
      isPolling: false,
      async startCopier({ chain, address, runId, positionSizePct, leverage, execute = false, label = null }) {
        const res = await api.startCopierSession({
          chain,
          address,
          run_id: runId,
          execute,
          position_size_pct: positionSizePct,
          leverage,
        });
        const next: CopierInstance = {
          sessionId: res.session_id,
          chain,
          address,
          runId,
          positionSizePct,
          leverage,
          execute,
          label,
          active: res.active,
          createdAt: Date.now(),
          status: toStatus(res),
          feed: [],
          lastTimestamp: undefined,
        };
        set((state) => ({
          copiers: { ...state.copiers, [res.session_id]: next },
        }));
        return next;
      },
      async stopCopier(sessionId) {
        try {
          const res = await api.stopCopierSession(sessionId);
          set((state) => {
            const current = state.copiers[sessionId];
            if (!current) return { copiers: state.copiers };
            return {
              copiers: {
                ...state.copiers,
                [sessionId]: { ...current, active: res.active, status: toStatus(res) },
              },
            };
          });
        } catch {
          set((state) => {
            const current = state.copiers[sessionId];
            if (!current) return { copiers: state.copiers };
            return { copiers: { ...state.copiers, [sessionId]: { ...current, active: false } } };
          });
        }
      },
      removeCopier(sessionId) {
        set((state) => {
          const next = { ...state.copiers };
          delete next[sessionId];
          return { copiers: next };
        });
      },
      async restoreSessions() {
        const locals = Object.values(get().copiers);
        if (!locals.length) return;
        const byWallet = new Map<string, { chain: ChainId; address: string }>();
        for (const c of locals) {
          byWallet.set(`${c.chain}:${c.address}`.toLowerCase(), { chain: c.chain, address: c.address });
        }
        for (const wallet of byWallet.values()) {
          let remote: CopierSessionStatus[] = [];
          try {
            remote = await api.listActiveCopierSessions(wallet.chain, wallet.address);
          } catch {
            continue;
          }
          const remoteIds = new Set(remote.map((r) => r.session_id));
          set((state) => {
            const next = { ...state.copiers };
            for (const r of remote) {
              const existing = next[r.session_id];
              if (existing) {
                next[r.session_id] = { ...existing, active: r.active, status: toStatus(r) };
              }
            }
            for (const sess of Object.values(next)) {
              if (sess.chain === wallet.chain && sess.address === wallet.address && !remoteIds.has(sess.sessionId)) {
                next[sess.sessionId] = { ...sess, active: false };
              }
            }
            return { copiers: next };
          });
        }
      },
      async pollActiveCopiers() {
        const { copiers, isPolling } = get();
        const active = Object.values(copiers).filter((c) => c.active);
        if (!active.length || isPolling) return;
        set({ isPolling: true });
        try {
          for (const sess of active) {
            try {
              const tradesRes = await api.getLiveTrades(sess.chain, sess.address, sess.lastTimestamp);
              set((state) => {
                const current = state.copiers[sess.sessionId];
                if (!current) return { copiers: state.copiers };
                const { feed, last } = mergeTrades(current.feed, tradesRes.trades || []);
                return {
                  copiers: {
                    ...state.copiers,
                    [sess.sessionId]: { ...current, feed, lastTimestamp: last },
                  },
                };
              });
            } catch {
              // swallow trade polling errors; status polling will mark inactivity if needed
            }
            try {
              const status = await api.getCopierSessionStatus(sess.sessionId);
              set((state) => {
                const current = state.copiers[sess.sessionId];
                if (!current) return { copiers: state.copiers };
                return {
                  copiers: {
                    ...state.copiers,
                    [sess.sessionId]: { ...current, active: status.active, status: toStatus(status) },
                  },
                };
              });
            } catch {
              // ignore status errors on a single tick
            }
          }
        } finally {
          set({ isPolling: false });
        }
      },
    }),
    {
      name: 'whale-copier-sessions',
      partialize: (state) => ({
        copiers: Object.fromEntries(
          Object.entries(state.copiers).map(([id, c]) => [
            id,
            { ...c, feed: c.feed.slice(-20) },
          ])
        ),
      }),
    }
  )
);
