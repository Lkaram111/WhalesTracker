import { useMemo } from 'react';
import type { ReactNode } from 'react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { formatPercent } from '@/lib/formatters';
import type { RoiPoint } from '@/types/api';

interface RoiChartProps {
  data: RoiPoint[];
  height?: number;
  actionSlot?: ReactNode;
}

export function RoiChart({ data, height = 300, actionSlot }: RoiChartProps) {
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
        <h3 className="text-sm font-medium text-muted-foreground">ROI History</h3>
        {actionSlot}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData}>
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
            tickFormatter={(value) => `${value.toFixed(0)}%`}
            width={60}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(222, 47%, 7%)',
              border: '1px solid hsl(217, 33%, 17%)',
              borderRadius: '8px',
              color: 'hsl(210, 40%, 98%)'
            }}
            formatter={(value: number) => [formatPercent(value), 'ROI']}
            labelStyle={{ color: 'hsl(215, 20%, 65%)' }}
          />
          <Line
            type="monotone"
            dataKey="roi_percent"
            stroke="hsl(160, 84%, 39%)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: 'hsl(160, 84%, 39%)' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
