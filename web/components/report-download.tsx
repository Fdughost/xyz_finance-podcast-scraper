'use client'

import { createElement } from 'react'
import Script from 'next/script'

export function ReportDownload({ reports }: { reports: string[] }) {
  return <>
    {createElement('report-download', { 'data-reports': JSON.stringify(reports) })}
    <Script src="/report-download.js" strategy="afterInteractive" />
  </>
}
