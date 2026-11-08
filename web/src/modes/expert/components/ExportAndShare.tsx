import React, { useState, useMemo } from 'react'
import type { LedgerParameter, ExpertSealedResultJson } from '../types'
import { getApiUrl } from '../../../api/config'

interface ExportAndShareProps {
  parameters: LedgerParameter[]
  sealedResult: ExpertSealedResultJson
}

export const ExportAndShare: React.FC<ExportAndShareProps> = ({
  parameters,
  sealedResult,
}) => {
  const [copiedLink, setCopiedLink] = useState(false)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  // Estimated PDF size based on assumption ledger rows (≈ 0.8 KB/row)
  const estimatedSizeKb = useMemo(() => {
    // Base size: equations, header, footer ≈ 40 KB
    // Each parameter row ≈ 0.8 KB
    // Compliance rules, citations ≈ 15 KB
    const baseSizeKb = 40
    const paramRowsKb = parameters.length * 0.8
    const extrasKb = 15
    return Math.round(baseSizeKb + paramRowsKb + extrasKb)
  }, [parameters])

  const estimatedSizeMb = (estimatedSizeKb / 1024).toFixed(1)
  const isLargeReport = estimatedSizeKb > 5 * 1024 // > 5 MB

  // 1. Export CSV
  const handleExportCsv = () => {
    const headers = [
      'Category',
      'Parameter Name',
      'Symbol',
      'Resolved Default',
      'Active Value',
      'Unit',
      'Is Overridden',
      'Provenance Source',
      'Citation',
    ]

    const rows = parameters.map((p) => [
      p.category,
      `"${p.name.replace(/"/g, '""')}"`,
      p.symbol,
      p.defaultValue,
      p.currentValue,
      `"${p.unit}"`,
      p.isOverridden ? 'YES' : 'NO',
      `"${p.provenance}"`,
      `"${p.citation.title} (${p.citation.source})"`,
    ])

    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    link.setAttribute('download', `Aavaran_Expert_Parameters_${ts}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // 2. Export JSON
  const handleExportJson = () => {
    const jsonStr = JSON.stringify(sealedResult, null, 2)
    const blob = new Blob([jsonStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const tsJson = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    link.setAttribute('download', `Aavaran_Expert_Report_${tsJson}.json`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // 3. Export Audit PDF — server-side WeasyPrint via /api/v1/report/audit
  // Uses the identical binary-response pattern from Bug 6 (RFQ PDF fix)
  const handleExportPdf = async () => {
    setDownloadingPdf(true)
    setDownloadError(null)
    try {
      const response = await fetch(getApiUrl('/api/v1/report/audit'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          result_data: sealedResult,
          report_type: 'expert',
        }),
      })

      if (!response.ok) {
        let errorDetail = 'Audit PDF generation failed'
        try {
          const err = await response.json()
          errorDetail = err.detail || errorDetail
        } catch {
          // Response body was not JSON
        }
        throw new Error(errorDetail)
      }

      // CRITICAL: get ArrayBuffer, not .text() or .json()
      // This is the same fix applied to the RFQ PDF in Bug 6
      const arrayBuffer = await response.arrayBuffer()
      const blob = new Blob([arrayBuffer], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)

      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
      const filename = `Aavaran_Expert_Audit_${timestamp}.pdf`

      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      // Clean up the object URL after a short delay
      setTimeout(() => URL.revokeObjectURL(url), 5000)
    } catch (err: any) {
      setDownloadError(err.message || 'Audit PDF generation failed')
    } finally {
      setDownloadingPdf(false)
    }
  }

  // 4. Shareable Link
  const handleCopyShareLink = async () => {
    try {
      const shareUrl = `${window.location.origin}${window.location.pathname}?mode=expert&result_id=${sealedResult.result_id}`
      await navigator.clipboard.writeText(shareUrl)
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 2500)
    } catch {
      // Fallback
    }
  }

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
              SEALED AUDIT EXPORT &amp; ARTIFACT REPLICATION
            </span>
          </div>
          <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            08 · Engineering Artifact Export &amp; Permanent Share
          </h3>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Export the complete decision state to spreadsheet CSV, machine-readable JSON, or official PDF audit report, or share a cryptographically sealed replay link.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* CSV Export */}
        <div className="p-4 border-2 border-ink bg-paper space-y-3 flex flex-col justify-between">
          <div>
            <div className="font-display text-sm uppercase text-ink">📊 SPREADSHEET CSV</div>
            <p className="font-body text-xs text-ink/70 mt-1">
              Full parameter table with symbols, defaults, overrides, units, and citation sources.
            </p>
          </div>
          <button
            type="button"
            onClick={handleExportCsv}
            className="w-full font-display text-xs uppercase py-2.5 px-3 bg-paper hover:bg-grey/40 border-2 border-ink shadow-[2px_2px_0_var(--ink)] cursor-pointer"
          >
            EXPORT CSV
          </button>
        </div>

        {/* JSON Export */}
        <div className="p-4 border-2 border-ink bg-paper space-y-3 flex flex-col justify-between">
          <div>
            <div className="font-display text-sm uppercase text-ink">📦 SEALED JSON</div>
            <p className="font-body text-xs text-ink/70 mt-1">
              Schema-valid SealedResult object matching the Python FastAPI backend contract.
            </p>
          </div>
          <button
            type="button"
            onClick={handleExportJson}
            className="w-full font-display text-xs uppercase py-2.5 px-3 bg-paper hover:bg-grey/40 border-2 border-ink shadow-[2px_2px_0_var(--ink)] cursor-pointer"
          >
            EXPORT JSON
          </button>
        </div>

        {/* PDF Export — now server-side via /api/v1/report/audit */}
        <div className="p-4 border-2 border-ink bg-violet/20 border-violet space-y-3 flex flex-col justify-between">
          <div>
            <div className="font-display text-sm uppercase text-ink">📑 AUDIT PDF SHEET</div>
            <p className="font-body text-xs text-ink/70 mt-1">
              Official engineering certificate with model equations, ledger, and academic citations.
            </p>
            {/* Step 4: Estimated size indicator */}
            <div className="mt-2 font-mono text-[10px] text-ink/60">
              Estimated size: ~{estimatedSizeKb > 1024 ? `${estimatedSizeMb} MB` : `${estimatedSizeKb} KB`}
            </div>
            {isLargeReport && (
              <div className="mt-1 text-[10px] font-bold text-red-700 bg-red-100 border border-red-300 px-2 py-1">
                ⚠ Large report — may take 20–30 seconds to generate.
              </div>
            )}
          </div>
          <div className="space-y-2">
            <button
              type="button"
              disabled={downloadingPdf}
              onClick={handleExportPdf}
              className="w-full font-display text-xs uppercase py-2.5 px-3 bg-violet text-ink border-2 border-ink shadow-[3px_3px_0_var(--ink)] hover:bg-violet/80 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {downloadingPdf ? 'GENERATING PDF…' : 'DOWNLOAD AUDIT PDF'}
            </button>
            {downloadError && (
              <div className="text-[10px] font-mono text-red-700 bg-red-50 border border-red-200 px-2 py-1.5">
                ✕ {downloadError}
              </div>
            )}
          </div>
        </div>

        {/* Shareable Link */}
        <div className="p-4 border-2 border-ink bg-paper space-y-3 flex flex-col justify-between">
          <div>
            <div className="font-display text-sm uppercase text-ink">🔗 PERMANENT LINK</div>
            <p className="font-body text-xs text-ink/70 mt-1">
              Unique replay URL preserving parameter overrides and stochastic state.
            </p>
          </div>
          <button
            type="button"
            onClick={handleCopyShareLink}
            className={`w-full font-display text-xs uppercase py-2.5 px-3 border-2 border-ink shadow-[2px_2px_0_var(--ink)] cursor-pointer transition-all ${
              copiedLink ? 'bg-lime text-ink' : 'bg-yellow text-ink hover:bg-yellow/80'
            }`}
          >
            {copiedLink ? '✓ LINK COPIED!' : 'COPY SHARE LINK'}
          </button>
        </div>
      </div>
    </div>
  )
}
