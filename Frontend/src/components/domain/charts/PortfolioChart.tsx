import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { formatUSD, formatPercent } from '@/lib/formatters';
import type { PortfolioPoint } from '@/types/api';

interface PortfolioChartProps {
  data: PortfolioPoint[];
  height?: number;
  actionSlot?: ReactNode;
}

const MODE_OPTIONS = [
  { value: 'balance', label: 'Balance' },
  { value: 'daily_pnl', label: 'Daily PnL %' },
] as const;

type ViewMode = (typeof MODE_OPTIONS)[number]['value'];

export function PortfolioChart({ data, height = 300, actionSlot }: PortfolioChartProps) {
  const [mode, setMode] = useState<ViewMode>('balance');
  const portfolioData = useMemo(() => {
    return [...data]
      .sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      )
      .map((point) => ({
        ...point,
        date: new Date(point.timestamp).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
        }),
        value_usd: Number(point.value_usd ?? 0),
      }));
  }, [data]);

  const pnlData = useMemo(() => {
    const result: Array<
      PortfolioPoint & { date: string; pnl_percent: number }
    > = [];
    let prevValue: number | null = null;
    for (const point of portfolioData) {
      let pnlPercent = 0;
      if (prevValue && prevValue > 0) {
        pnlPercent = ((point.value_usd - prevValue) / prevValue) * 100;
      }
      result.push({
        ...point,
        pnl_percent: pnlPercent,
      });
      prevValue = point.value_usd;
    }
    return result;
  }, [portfolioData]);

  const displayData = mode === 'daily_pnl' ? pnlData : portfolioData;

  const renderModeButtons = (
    <div className="flex gap-1">
      {MODE_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => setMode(option.value)}
          className={`rounded-md border px-2 py-1 text-xs font-medium transition-colors ${
            mode === option.value
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border text-muted-foreground hover:bg-muted'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="card-glass rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-muted-foreground">
          {mode === 'daily_pnl' ? 'Daily PnL' : 'Portfolio Value'}
        </h3>
        <div className="flex items-center gap-2">
          {renderModeButtons}
          {actionSlot}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        {mode === 'daily_pnl' ? (
          <LineChart data={displayData}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="hsl(217, 33%, 17%)"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              stroke="hsl(215, 20%, 65%)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="hsl(215, 20%, 65%)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => formatPercent(value)}
              width={60}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(222, 47%, 7%)',
                border: '1px solid hsl(217, 33%, 17%)',
                borderRadius: '8px',
                color: 'hsl(210, 40%, 98%)',
              }}
              formatter={(value: number) => [formatPercent(value), 'Daily PnL %']}
              labelStyle={{ color: 'hsl(215, 20%, 65%)' }}
            />
            <Line
              type="monotone"
              dataKey="pnl_percent"
              stroke="hsl(160, 84%, 39%)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: 'hsl(160, 84%, 39%)' }}
            />
          </LineChart>
        ) : (
          <AreaChart data={displayData}>
            <defs>
              <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor="hsl(217, 91%, 60%)"
                  stopOpacity={0.3}
                />
                <stop
                  offset="100%"
                  stopColor="hsl(217, 91%, 60%)"
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="hsl(217, 33%, 17%)"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              stroke="hsl(215, 20%, 65%)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="hsl(215, 20%, 65%)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => formatUSD(value)}
              width={80}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(222, 47%, 7%)',
                border: '1px solid hsl(217, 33%, 17%)',
                borderRadius: '8px',
                color: 'hsl(210, 40%, 98%)',
              }}
              formatter={(value: number) => [
                formatUSD(value),
                'Portfolio Value',
              ]}
              labelStyle={{ color: 'hsl(215, 20%, 65%)' }}
            />
            <Area
              type="monotone"
              dataKey="value_usd"
              stroke="hsl(217, 91%, 60%)"
              strokeWidth={2}
              fill="url(#portfolioGradient)"
            />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
