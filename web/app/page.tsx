import { Suspense } from 'react'
import { getPodcastData } from '@/lib/data'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PodcastTable } from '@/components/podcast-table'
import { SubscriptionBarChart } from '@/components/bar-chart'
import { TrendChart } from '@/components/trend-chart'
import { ReportDownload } from '@/components/report-download'

export const dynamic = 'force-dynamic'

export default async function Home() {
  const data = await getPodcastData()

  return (
    <div className="min-h-screen bg-muted/30">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-background/95 backdrop-blur border-b">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold">📻 播客日报</span>
            <span className="text-sm text-muted-foreground hidden sm:inline">公募基金播客监控</span>
          </div>
          <ReportDownload reports={data.reports} />
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Stats bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-2xl font-bold">{data.podcasts.length}</div>
              <div className="text-xs text-muted-foreground mt-0.5">监控播客数</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-2xl font-bold">
                {data.podcasts.reduce((s, p) => s + p.subs, 0).toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">总订阅数</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-2xl font-bold">{data.podcasts[0]?.name ?? '—'}</div>
              <div className="text-xs text-muted-foreground mt-0.5">订阅榜首</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-2xl font-bold">{data.date}</div>
              <div className="text-xs text-muted-foreground mt-0.5">数据日期</div>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">订阅排行 Top 10</CardTitle>
            </CardHeader>
            <CardContent>
              <Suspense fallback={<div className="h-[280px] flex items-center justify-center text-muted-foreground text-sm">加载中...</div>}>
                <SubscriptionBarChart podcasts={data.podcasts} />
              </Suspense>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">订阅趋势</CardTitle>
            </CardHeader>
            <CardContent>
              <Suspense fallback={<div className="h-[280px] flex items-center justify-center text-muted-foreground text-sm">加载中...</div>}>
                <TrendChart trend={data.trend} />
              </Suspense>
            </CardContent>
          </Card>
        </div>

        {/* Data table */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">播客数据明细</CardTitle>
          </CardHeader>
          <CardContent>
            <PodcastTable podcasts={data.podcasts} />
          </CardContent>
        </Card>

        <footer className="text-center text-xs text-muted-foreground pb-4">
          数据来源：小宇宙 · 更新于 {data.generated_at}
        </footer>
      </main>
    </div>
  )
}
