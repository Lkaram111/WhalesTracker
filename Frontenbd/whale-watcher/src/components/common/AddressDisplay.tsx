import { useState } from 'react';
import { Copy, Check, ExternalLink } from 'lucide-react';
import { formatAddress } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { ChainId } from '@/types/api';

interface AddressDisplayProps {
  address: string;
  chain?: ChainId;
  truncate?: boolean;
  showCopy?: boolean;
  showExternalLink?: boolean;
  className?: string;
}

const explorerUrls: Record<ChainId, string> = {
  ethereum: 'https://etherscan.io/address/',
  bitcoin: 'https://mempool.space/address/',
  hyperliquid: 'https://app.hyperliquid.xyz/explorer/address/'
};

export function AddressDisplay({ 
  address, 
  chain,
  truncate = true, 
  showCopy = true,
  showExternalLink = true,
  className 
}: AddressDisplayProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const displayAddress = truncate ? formatAddress(address) : address;
  const explorerUrl = chain ? `${explorerUrls[chain]}${address}` : null;

  return (
    <div className={cn('inline-flex items-center gap-2', className)}>
      <span className="font-mono text-sm">{displayAddress}</span>
      {showCopy && (
        <button
          onClick={handleCopy}
          className="flex h-6 w-6 items-center justify-center rounded hover:bg-muted transition-colors"
          aria-label="Copy address"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-success" />
          ) : (
            <Copy className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </button>
      )}
      {showExternalLink && explorerUrl && (
        <a
          href={explorerUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex h-6 w-6 items-center justify-center rounded hover:bg-muted transition-colors"
          aria-label="View on explorer"
        >
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
        </a>
      )}
    </div>
  );
}
