'use client'

import { useState } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { DeltaBadge } from './delta-badge'
import { Podcast } from '@/lib/types'

interface PodcastTableProps {
  podcasts: Podcast[]
}

export function PodcastTable({ podcasts }: PodcastTableProps) {
  const [search, setSearch] = useState('')

  const filtered = podcasts.filter(
    (p) =>
      p.name.includes(search) ||
      p.category.includes(search) ||
      p.company.includes(search) ||
      p.latest_episode.includes(search)
  )

  return (
    <div className="space-y-3">
      <Input
        placeholder="搜索播客名称、公司或单集..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      {/* Desktop table */}
      <div className="hidden md:block rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead className="w-12 text-center">#</TableHead>
              <TableHead>节目名称</TableHead>
              <TableHead>分类</TableHead>
              <TableHead>机构名称</TableHead>
              <TableHead className="text-right">订阅数</TableHead>
              <TableHead className="text-right">7日增量</TableHead>
              <TableHead className="text-right">30日增量</TableHead>
              <TableHead>最新单集</TableHead>
              <TableHead className="text-right">播放数</TableHead>
              <TableHead className="text-right">互动</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((p) => (
              <TableRow key={p.rank} className="hover:bg-muted/30">
                <TableCell className="text-center text-muted-foreground text-sm">{p.rank}</TableCell>
                <TableCell className="font-medium">{p.name}</TableCell>
                <TableCell className="text-muted-foreground text-sm">{p.category}</TableCell>
                <TableCell className="text-muted-foreground text-sm">{p.company}</TableCell>
                <TableCell className="text-right font-mono">{p.subs.toLocaleString()}</TableCell>
                <TableCell className="text-right font-mono text-sm">
                  <DeltaBadge value={p.delta_7d} />
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  <DeltaBadge value={p.delta_30d} />
                </TableCell>
                <TableCell className="max-w-[200px] truncate text-sm text-muted-foreground" title={p.latest_episode}>
                  {p.latest_episode}
                </TableCell>
                <TableCell className="text-right text-sm font-mono">{p.plays.toLocaleString()}</TableCell>
                <TableCell className="text-right text-sm font-mono">{p.interactions.toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3">
        {filtered.map((p) => (
          <Card key={p.rank}>
            <CardContent className="pt-4 pb-3 px-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl font-bold text-muted-foreground/40 leading-none mt-1 w-7 shrink-0">
                  {p.rank}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold truncate">{p.name}</div>
                  <div className="text-sm text-muted-foreground">{p.category}{p.company ? ` · ${p.company}` : ''}</div>
                  <div className="mt-2 grid grid-cols-4 gap-2 text-center">
                    <div>
                      <div className="text-base font-bold font-mono">{p.subs.toLocaleString()}</div>
                      <div className="text-xs text-muted-foreground">订阅数</div>
                    </div>
                    <div>
                      <div className="text-base font-mono"><DeltaBadge value={p.delta_7d} /></div>
                      <div className="text-xs text-muted-foreground">7日</div>
                    </div>
                    <div>
                      <div className="text-base font-mono"><DeltaBadge value={p.delta_30d} /></div>
                      <div className="text-xs text-muted-foreground">30日</div>
                    </div>
                    <div>
                      <div className="text-base font-mono">{p.plays.toLocaleString()}</div>
                      <div className="text-xs text-muted-foreground">播放</div>
                    </div>
                  </div>
                  {p.latest_episode && (
                    <div className="mt-2 text-xs text-muted-foreground truncate">
                      📻 {p.latest_episode}
                    </div>
                  )}
                  <div className="mt-1 text-xs text-muted-foreground">
                    {p.latest_date} · 互动 {p.interactions}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
