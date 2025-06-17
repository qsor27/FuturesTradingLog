import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

const PnLGraph = ({ data, timeframe }) => {
  // Transform the data for the graph
  const chartData = data.map(item => ({
    period: item.period,
    pnl: item.total_pnl,
  })).reverse(); // Reverse to show oldest to newest

  return (
    <Card className="w-full mt-4">
      <CardHeader className="pb-2">
        <CardTitle>Profit/Loss Over Time ({timeframe})</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-96 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="period" 
                angle={-45}
                textAnchor="end"
                height={60}
                interval={0}
              />
              <YAxis 
                tickFormatter={(value) => `$${value.toLocaleString()}`}
              />
              <Tooltip
                formatter={(value) => [`$${value.toLocaleString()}`, 'P&L']}
                labelFormatter={(label) => `Period: ${label}`}
              />
              <Line
                type="monotone"
                dataKey="pnl"
                stroke="#2563eb"
                strokeWidth={2}
                dot={{
                  fill: '#2563eb',
                  stroke: '#2563eb',
                  strokeWidth: 1,
                  r: 4,
                }}
                activeDot={{
                  fill: '#2563eb',
                  stroke: '#ffffff',
                  strokeWidth: 2,
                  r: 6,
                }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
};

export default PnLGraph;