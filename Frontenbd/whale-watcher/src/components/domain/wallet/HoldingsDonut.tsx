import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { formatUSD } from '@/lib/formatters';
import type { Holding } from '@/types/api';

const COLORS = [
  'hsl(217, 91%, 60%)',
  'hsl(160, 84%, 39%)',
  'hsl(43, 89%, 60%)',
  'hsl(280, 80%, 70%)',
  'hsl(12, 80%, 64%)',
  'hsl(210, 34%, 63%)',
];

interface HoldingsDonutProps {
  holdings: Holding[];
  height?: number;
}

export function HoldingsDonut({ holdings, height = 320 }: HoldingsDonutProps) {
  const totalValue = holdings.reduce((sum, h) => sum + h.value_usd, 0);
  const chartData = holdings.map((holding, index) => ({
    name: holding.asset_symbol,
    value: holding.value_usd,
    percent: holding.portfolio_percent,
    color: COLORS[index % COLORS.length],
  }));

  return (
    <div className="card-glass rounded-xl p-4 h-full">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-medium text-foreground">Holdings Breakdown</h3>
          <p className="text-xs text-muted-foreground">Share of wallet by USD value</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-muted-foreground">Total Value</p>
          <p className="text-sm font-semibold text-foreground">{formatUSD(totalValue)}</p>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-5 gap-4 items-center">
        <div className="sm:col-span-3 h-full" style={{ minHeight: height }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(222, 47%, 7%)',
                  border: '1px solid hsl(217, 33%, 17%)',
                  borderRadius: '8px',
                  color: 'hsl(210, 40%, 98%)',
                }}
                formatter={(value: number, _name, entry) => [
                  formatUSD(value),
                  `${entry.payload.name} (${entry.payload.percent.toFixed(1)}%)`,
                ]}
              />
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                innerRadius="60%"
                outerRadius="90%"
                paddingAngle={2}
                stroke="hsl(222, 47%, 7%)"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`${entry.name}-${index}`} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="sm:col-span-2 space-y-3">
          {chartData.map((holding, index) => (
            <div key={`${holding.name}-${index}`} className="flex items-center justify-between rounded-lg bg-muted/30 p-2">
              <div className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: holding.color }}
                />
                <span className="text-sm font-medium text-foreground">{holding.name}</span>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">{holding.percent.toFixed(1)}%</p>
                <p className="text-xs text-muted-foreground">{formatUSD(holding.value)}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
