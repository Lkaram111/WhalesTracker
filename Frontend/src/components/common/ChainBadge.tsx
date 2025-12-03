import { cn } from '@/lib/utils';
import { getChainColor } from '@/lib/formatters';
import type { ChainId } from '@/types/api';

interface ChainBadgeProps {
  chain: ChainId;
  size?: 'sm' | 'md';
}

const chainLabels: Record<ChainId, string> = {
  ethereum: 'ETH',
  bitcoin: 'BTC',
  hyperliquid: 'HL'
};

const chainIcons: Record<ChainId, string> = {
  ethereum: '⟠',
  bitcoin: '₿',
  hyperliquid: '◆'
};

export function ChainBadge({ chain, size = 'sm' }: ChainBadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-md border font-medium',
      getChainColor(chain),
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
    )}>
      <span>{chainIcons[chain]}</span>
      <span>{chainLabels[chain]}</span>
    </span>
  );
}
