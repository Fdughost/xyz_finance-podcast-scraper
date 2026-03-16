'use client'

import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { TrendData } from '@/lib/types'
import { Badge } from '@/components/ui/badge'

interface TrendChartProps {
  trend: TrendData
}

const LINE_COLORS = [
  '#6366f1', '#f43f5e', '#f97316', '#22c55e', '#06b6d4',
  '#a855f7', '#eab308', '#ec4899', '#14b8a6', '#8b5cf6',
]

export function TrendChart({ trend }: TrendChartProps) {
  const [selected, setSelected] = useState<Set<string>>(
    new Set(trend.series.slice(0, 5).map((s) => s.name))
  )

  const chartData = trend.dates.map((date, i) => {
    const point: Record<string, string | number | null> = { date: date.slice(5) } // MM-DD
    trend.series.forEach((s) => {
      point[s.name] = s.data[i] ?? null
    })
    return point
  })

  const toggleSeries = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        if (next.size > 1) next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {trend.series.map((s, i) => (
          <Badge
            key={s.name}
            variant={selected.has(s.name) ? 'default' : 'outline'}
            className="cursor-pointer text-xs"
            style={
              selected.has(s.name)
                ? { background: LINE_COLORS[i % LINE_COLORS.length], borderColor: LINE_COLORS[i % LINE_COLORS.length] }
                : { color: LINE_COLORS[i % LINE_COLORS.length], borderColor: LINE_COLORS[i % LINE_COLORS.length] }
            }
            onClick={() => toggleSeries(s.name)}
          >
            {s.name}
          </Badge>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            interval="preserveStartEnd"
          />
          <YAxis
            tickFormatter={(v) => `${(v / 10000).toFixed(0)}w`}
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value, name) => [typeof value === 'number' ? value.toLocaleString() : value, name]}
            contentStyle={{
              borderRadius: '8px',
              border: '1px solid hsl(var(--border))',
              background: 'hsl(var(--background))',
              fontSize: 12,
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, display: 'none' }}
          />
          {trend.series.map((s, i) =>
            selected.has(s.name) ? (
              <Line
                key={s.name}
                type="monotone"
                dataKey={s.name}
                stroke={LINE_COLORS[i % LINE_COLORS.length]}
                strokeWidth={2}
                dot={false}
                connectNulls={false}
              />
            ) : null
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
