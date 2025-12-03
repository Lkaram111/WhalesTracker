import { useMemo } from 'react';
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
  AreaChart
} from 'recharts';
import { formatUSD } from '@/lib/formatters';
import type { PortfolioPoint } from '@/types/api';

interface PortfolioChartProps {
  data: PortfolioPoint[];
  height?: number;
  actionSlot?: ReactNode;
}

export function PortfolioChart({ data, height = 300, actionSlot }: PortfolioChartProps) {
  const chartData = useMemo(() => {
    return data.map(point => ({
      ...point,
      date: new Date(point.timestamp).toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
      })
    }));
  }, [data]);

  return (
    <div className="card-glass rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-muted-foreground">Portfolio Value</h3>
        {actionSlot}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(217, 91%, 60%)" stopOpacity={0.3} />
              <stop offset="100%" stopColor="hsl(217, 91%, 60%)" stopOpacity={0} />
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
              color: 'hsl(210, 40%, 98%)'
            }}
            formatter={(value: number) => [formatUSD(value), 'Portfolio Value']}
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
      </ResponsiveContainer>
    </div>
  );
}
