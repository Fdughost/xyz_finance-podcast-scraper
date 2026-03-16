import { PodcastData } from './types'
import path from 'path'

export async function getPodcastData(): Promise<PodcastData> {
  // Server component: read from local filesystem (works in both dev and Vercel)
  const fs = await import('fs')
  const filePath = path.join(process.cwd(), 'public', 'data.json')
  const raw = fs.readFileSync(filePath, 'utf-8')
  return JSON.parse(raw) as PodcastData
}
