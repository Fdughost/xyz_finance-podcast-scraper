'use client'

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { Podcast } from '@/lib/types'

interface SubscriptionBarChartProps {
  podcasts: Podcast[]
}

const COLORS = [
  '#6366f1', '#8b5cf6', '#a855f7', '#ec4899', '#f43f5e',
  '#f97316', '#eab308', '#22c55e', '#14b8a6', '#06b6d4',
]

export function SubscriptionBarChart({ podcasts }: SubscriptionBarChartProps) {
  const top10 = podcasts.slice(0, 10).map((p) => ({
    name: p.name.length > 6 ? p.name.slice(0, 6) + '…' : p.name,
    fullName: p.name,
    subs: p.subs,
  }))

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={top10} margin={{ top: 5, right: 10, left: 10, bottom: 40 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }}
          angle={-30}
          textAnchor="end"
          interval={0}
        />
        <YAxis
          tickFormatter={(v) => `${(v / 10000).toFixed(0)}w`}
          tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(value, _name, props) => [
            typeof value === 'number' ? value.toLocaleString() : value,
            props.payload?.fullName ?? _name,
          ]}
          contentStyle={{
            borderRadius: '8px',
            border: '1px solid hsl(var(--border))',
            background: 'hsl(var(--background))',
            fontSize: 12,
          }}
          labelStyle={{ display: 'none' }}
        />
        <Bar dataKey="subs" radius={[4, 4, 0, 0]}>
          {top10.map((_entry, index) => (
            <Cell key={index} fill={COLORS[index % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
