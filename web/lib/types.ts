export interface Podcast {
  rank: number
  name: string
  company: string
  subs: number
  delta_7d: number | null
  delta_30d: number | null
  latest_episode: string
  latest_date: string
  plays: number
  interactions: number
  duration: string
}

export interface TrendSeries {
  name: string
  data: (number | null)[]
}

export interface TrendData {
  dates: string[]
  series: TrendSeries[]
}

export interface PodcastData {
  date: string
  generated_at: string
  podcasts: Podcast[]
  trend: TrendData
  reports: string[]
}
