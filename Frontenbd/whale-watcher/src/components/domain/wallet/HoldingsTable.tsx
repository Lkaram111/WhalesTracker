import { formatUSD, formatNumber } from '@/lib/formatters';
import { ChainBadge } from '@/components/common/ChainBadge';
import type { Holding } from '@/types/api';

interface HoldingsTableProps {
  holdings: Holding[];
}

export function HoldingsTable({ holdings }: HoldingsTableProps) {
  return (
    <div className="card-glass rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-sm font-medium text-foreground">Holdings</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Asset
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Chain
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Amount
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Value
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Portfolio %
              </th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((holding, index) => (
              <tr 
                key={`${holding.asset_symbol}-${holding.chain}-${index}`}
                className="border-b border-border/50"
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-xs font-bold">
                      {holding.asset_symbol.slice(0, 2)}
                    </div>
                    <div>
                      <p className="font-medium text-foreground">{holding.asset_symbol}</p>
                      <p className="text-xs text-muted-foreground">{holding.asset_name}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <ChainBadge chain={holding.chain} />
                </td>
                <td className="px-4 py-3 text-right font-mono text-sm text-muted-foreground">
                  {formatNumber(parseFloat(holding.amount))}
                </td>
                <td className="px-4 py-3 text-right font-medium text-foreground">
                  {formatUSD(holding.value_usd)}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-primary rounded-full"
                        style={{ width: `${holding.portfolio_percent}%` }}
                      />
                    </div>
                    <span className="text-sm text-muted-foreground w-12 text-right">
                      {holding.portfolio_percent.toFixed(1)}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
