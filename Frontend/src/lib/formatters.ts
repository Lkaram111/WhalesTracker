export const formatUSD = (value: number): string => {
  if (Math.abs(value) >= 1_000_000_000) {
    return `$${(value / 1_000_000_000).toFixed(2)}B`;
  }
  if (Math.abs(value) >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `$${(value / 1_000).toFixed(1)}K`;
  }
  return `$${value.toFixed(2)}`;
};

export const formatUSDExact = (
  value: number,
  minimumFractionDigits = 2,
  maximumFractionDigits = 8
): string => {
  return `$${value.toLocaleString('en-US', {
    minimumFractionDigits,
    maximumFractionDigits,
  })}`;
};

export const formatNumber = (value: number): string => {
  if (Math.abs(value) >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)}B`;
  }
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }
  return value.toFixed(2);
};

export const formatPercent = (value: number): string => {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
};

export const formatAddress = (address: string, chars: number = 6): string => {
  if (address.length <= chars * 2 + 3) return address;
  return `${address.slice(0, chars)}...${address.slice(-chars)}`;
};

const parseTimestamp = (timestamp: string): Date => {
  // If no timezone info, assume UTC to avoid local misinterpretation
  const hasTz = /[zZ]|[+-]\d\d:?\d\d$/.test(timestamp);
  return new Date(hasTz ? timestamp : `${timestamp}Z`);
};

export const formatTimeAgo = (timestamp: string): string => {
  const now = new Date();
  const date = parseTimestamp(timestamp);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
};

export const formatDate = (timestamp: string): string => {
  return parseTimestamp(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const getChainColor = (chain: string): string => {
  switch (chain) {
    case 'ethereum':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'bitcoin':
      return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    case 'hyperliquid':
      return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    default:
      return 'bg-muted text-muted-foreground border-border';
  }
};

export const getTypeColor = (type: string): string => {
  switch (type) {
    case 'holder':
      return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    case 'trader':
      return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30';
    case 'holder_trader':
      return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    default:
      return 'bg-muted text-muted-foreground border-border';
  }
};

export const getEventTypeIcon = (type: string): string => {
  switch (type) {
    case 'large_swap':
      return '🔄';
    case 'large_transfer':
      return '📤';
    case 'exchange_flow':
      return '🏦';
    case 'perp_trade':
      return '📈';
    default:
      return '💰';
  }
};
