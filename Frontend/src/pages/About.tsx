import { Waves, Database, Shield, AlertTriangle } from 'lucide-react';

export default function About() {
  return (
    <div className="space-y-8 animate-fade-up max-w-3xl">
      {/* Page Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/20 glow-primary">
          <Waves className="h-7 w-7 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">About WhaleTracker</h1>
          <p className="text-muted-foreground">Track the smartest money in crypto</p>
        </div>
      </div>

      {/* What is a Whale */}
      <div className="card-glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-3">What is a Whale?</h2>
        <p className="text-muted-foreground leading-relaxed">
          In cryptocurrency markets, a "whale" refers to an individual or entity that holds a significantly 
          large amount of cryptocurrency. These large holders can influence market prices through their 
          trades and are often closely watched by other traders. WhaleTracker monitors wallets with 
          substantial holdings across Ethereum, Bitcoin, and Hyperliquid to provide insights into their 
          trading behavior and performance.
        </p>
      </div>

      {/* Data Sources */}
      <div className="card-glass rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
            <Database className="h-5 w-5 text-accent" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">Data Sources</h2>
        </div>
        <div className="space-y-3 text-muted-foreground">
          <p>WhaleTracker aggregates data from multiple sources:</p>
          <ul className="list-disc list-inside space-y-2 ml-2">
            <li>
              <span className="text-foreground font-medium">Ethereum</span> — On-chain data from 
              the Ethereum blockchain, tracking DEX trades, transfers, and DeFi interactions
            </li>
            <li>
              <span className="text-foreground font-medium">Bitcoin</span> — UTXO-based tracking 
              of large Bitcoin holdings and movements
            </li>
            <li>
              <span className="text-foreground font-medium">Hyperliquid</span> — Perpetual futures 
              trading data including positions, PnL, and liquidations
            </li>
            <li>
              <span className="text-foreground font-medium">Exchange Flows</span> — Deposits and 
              withdrawals to major centralized exchanges
            </li>
          </ul>
        </div>
      </div>

      {/* Limitations */}
      <div className="card-glass rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-warning/10">
            <Shield className="h-5 w-5 text-warning" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">Limitations</h2>
        </div>
        <ul className="space-y-3 text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-warning mt-1">•</span>
            <span>Historical data may be incomplete for wallets that were not tracked from their inception</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-warning mt-1">•</span>
            <span>ROI calculations are estimates based on available on-chain data and may not reflect actual performance</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-warning mt-1">•</span>
            <span>Some transactions may be misclassified or attributed to the wrong strategy type</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-warning mt-1">•</span>
            <span>Off-chain activities (CEX trading, OTC deals) are not tracked</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-warning mt-1">•</span>
            <span>Real-time data may have slight delays depending on blockchain confirmation times</span>
          </li>
        </ul>
      </div>

      {/* Disclaimer */}
      <div className="card-glass rounded-xl p-6 border-destructive/30">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-destructive/10">
            <AlertTriangle className="h-5 w-5 text-destructive" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">Disclaimer</h2>
        </div>
        <div className="space-y-3 text-muted-foreground text-sm">
          <p>
            <span className="text-foreground font-medium">This is not financial advice.</span> WhaleTracker 
            is a data aggregation and visualization tool intended for informational and educational purposes only.
          </p>
          <p>
            Past performance of any wallet or trading strategy does not guarantee future results. Cryptocurrency 
            markets are highly volatile and involve substantial risk of loss. Always conduct your own research 
            and consider your financial situation before making any investment decisions.
          </p>
          <p>
            WhaleTracker makes no representations or warranties regarding the accuracy, completeness, or timeliness 
            of the information provided. Users assume all responsibility for their use of this information.
          </p>
        </div>
      </div>

      {/* Version */}
      <div className="text-center text-xs text-muted-foreground py-4">
        WhaleTracker v1.0.0 • Built with ❤️ for the crypto community
      </div>
    </div>
  );
}
