import { FormEvent, useMemo, useState } from 'react';
import { Plus, Sparkles, Loader2 } from 'lucide-react';
import { api } from '@/lib/apiClient';
import { cn } from '@/lib/utils';
import type { ChainId, WhaleCreateRequest, WhaleSummary, WhaleType } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { toast } from '@/components/ui/sonner';

type Props = {
  className?: string;
  onCreated?: (whale: WhaleSummary) => void;
  initialChain?: ChainId;
};

const chainOptions: { value: ChainId; label: string }[] = [
  { value: 'ethereum', label: 'Ethereum' },
  { value: 'bitcoin', label: 'Bitcoin' },
  { value: 'hyperliquid', label: 'Hyperliquid' },
];

const typeOptions: { value: WhaleType | 'auto'; label: string }[] = [
  { value: 'auto', label: 'Auto (classify later)' },
  { value: 'holder', label: 'Holder' },
  { value: 'trader', label: 'Trader' },
  { value: 'holder_trader', label: 'Holder + Trader' },
];

export function AddWhaleForm({ className, onCreated, initialChain = 'ethereum' }: Props) {
  const [address, setAddress] = useState('');
  const [chain, setChain] = useState<ChainId>(initialChain);
  const [type, setType] = useState<WhaleType | 'auto'>('auto');
  const [labels, setLabels] = useState('');
  const [loading, setLoading] = useState(false);

  const parsedLabels = useMemo(
    () => labels.split(',').map((l) => l.trim()).filter(Boolean),
    [labels]
  );

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!address.trim()) {
      toast.error('Please enter a wallet address or account id');
      return;
    }
    setLoading(true);
    try {
      const payload: WhaleCreateRequest = {
        address: address.trim(),
        chain,
        labels: parsedLabels,
        type: type === 'auto' ? undefined : type,
      };
      const whale = await api.createWhale(payload);
      toast.success(`Tracking ${whale.address} on ${whale.chain}`, {
        description: whale.labels?.includes('hyperliquid')
          ? 'Detected Hyperliquid account from ledger'
          : 'Whale added; holdings/metrics will refresh shortly',
      });
      setAddress('');
      setLabels('');
      onCreated?.(whale);
      // Keep chain selection aligned with what was added
      setChain(whale.chain as ChainId);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to add whale';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={cn('card-glass rounded-xl p-4', className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Track a new whale</h3>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Paste any ETH/BTC address or Hyperliquid account. Hyperliquid is auto-detected via ledger lookup.
          </p>
        </div>
      </div>
      <form onSubmit={handleSubmit} className="mt-3 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="md:col-span-2 space-y-1">
          <Label htmlFor="whale-address">Address / Account</Label>
          <Input
            id="whale-address"
            placeholder="0x... or hyperliquid handle"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label>Chain</Label>
          <Select value={chain} onValueChange={(v) => setChain(v as ChainId)}>
            <SelectTrigger>
              <SelectValue placeholder="Select chain" />
            </SelectTrigger>
            <SelectContent>
              {chainOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label>Type</Label>
          <Select value={type} onValueChange={(v) => setType(v as WhaleType | 'auto')}>
            <SelectTrigger>
              <SelectValue placeholder="Auto" />
            </SelectTrigger>
            <SelectContent>
              {typeOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="md:col-span-3 space-y-1">
          <Label htmlFor="whale-labels">
            Labels (optional, comma separated)
          </Label>
          <Input
            id="whale-labels"
            placeholder="exchange, fund, vc"
            value={labels}
            onChange={(e) => setLabels(e.target.value)}
          />
        </div>
        <div className="flex items-end">
          <Button type="submit" className="w-full md:w-auto" disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
            Add to tracker
          </Button>
        </div>
      </form>
    </div>
  );
}
