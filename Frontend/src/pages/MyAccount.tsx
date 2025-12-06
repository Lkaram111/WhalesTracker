import WhaleDetail from './WhaleDetail';
import { MY_HYPERLIQUID_ADDRESS } from '@/config';

export default function MyAccount() {
  if (!MY_HYPERLIQUID_ADDRESS) {
    return (
      <div className="max-w-lg mx-auto mt-24 space-y-3 text-center animate-fade-up">
        <h1 className="text-2xl font-semibold">My Hyperliquid Account</h1>
        <p className="text-muted-foreground">
          Set <code>HYPERLIQUID_ADDRESS</code> in your <code>.env</code> to see your own performance.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="text-2xl font-bold text-foreground">My Hyperliquid Account</h1>
        <p className="text-muted-foreground">
          Your personal performance, positions, and trade history. Copied whales and profit attribution coming soon.
        </p>
      </div>

      <div className="card-glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-1">Copied Whales & Copier PnL</h2>
        <p className="text-sm text-muted-foreground">
          This space will summarize which whales you are copying and the profits attributed to each entry. Add them in Settings
          → Whales to start tracking.
        </p>
      </div>

      <WhaleDetail chainOverride="hyperliquid" addressOverride={MY_HYPERLIQUID_ADDRESS} hideBackLink />
    </div>
  );
}
