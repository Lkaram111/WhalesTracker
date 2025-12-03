import { cn } from '@/lib/utils';
import { getTypeColor } from '@/lib/formatters';

interface TypeBadgeProps {
  type: 'holder' | 'trader' | 'holder_trader';
  size?: 'sm' | 'md';
}

const typeLabels: Record<string, string> = {
  holder: 'Holder',
  trader: 'Trader',
  holder_trader: 'Holder + Trader'
};

export function TypeBadge({ type, size = 'sm' }: TypeBadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center rounded-md border font-medium',
      getTypeColor(type),
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'
    )}>
      {typeLabels[type]}
    </span>
  );
}
