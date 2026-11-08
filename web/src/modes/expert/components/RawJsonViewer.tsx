import React, { useState } from 'react'
import type { ExpertSealedResultJson } from '../types'

interface RawJsonViewerProps {
  sealedResult: ExpertSealedResultJson
}

export const RawJsonViewer: React.FC<RawJsonViewerProps> = ({ sealedResult }) => {
  const [searchTerm, setSearchTerm] = useState('')
  const [copied, setCopied] = useState(false)

  const jsonString = JSON.stringify(sealedResult, null, 2)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(jsonString)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
    }
  }

  // Filter lines if search term is provided
  const lines = jsonString.split('\n')
  const matchedLineCount = searchTerm
    ? lines.filter((l) => l.toLowerCase().includes(searchTerm.toLowerCase())).length
    : lines.length

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
              RAW MACHINE-READABLE SCHEMA (SECTION 9)
            </span>
            <span className="font-mono text-xs font-bold text-ink/70">
              {lines.length} LINES · {new Blob([jsonString]).size} BYTES
            </span>
          </div>
          <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            09 · Raw SealedResult JSON Object
          </h3>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Complete cryptographic decision object, schema-compatible with the Aavaran backend API contract.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleCopy}
            className={`font-display text-xs uppercase px-4 py-2 border-2 border-ink shadow-[2px_2px_0_var(--ink)] cursor-pointer transition-all ${
              copied ? 'bg-lime text-ink' : 'bg-yellow text-ink hover:bg-yellow/80'
            }`}
          >
            {copied ? '✓ JSON COPIED!' : '📋 COPY RAW JSON'}
          </button>
        </div>
      </div>

      {/* Search Input Bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <input
            type="text"
            placeholder="Search keys or values in JSON (e.g., 'p50', 'fssai', 'thickness_um')..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full border-2 border-ink p-2 font-mono text-xs bg-paper text-ink pl-8"
          />
          <span className="absolute left-2.5 top-2 text-xs">🔍</span>
        </div>
        {searchTerm && (
          <span className="font-mono text-xs text-ink/70 shrink-0">
            {matchedLineCount} matching lines
          </span>
        )}
      </div>

      {/* JSON Display Screen */}
      <div className="border-3 border-ink bg-[#0B0B0B] text-[#FFFDF2] p-4 font-mono text-xs overflow-x-auto max-h-[460px] overflow-y-auto leading-relaxed selection:bg-violet selection:text-ink">
        <pre className="m-0">
          <code>
            {lines.map((line, idx) => {
              const isMatch = searchTerm && line.toLowerCase().includes(searchTerm.toLowerCase())
              return (
                <div
                  key={idx}
                  className={`flex ${isMatch ? 'bg-violet/30 text-yellow font-bold' : ''}`}
                >
                  <span className="w-10 text-right pr-3 select-none text-ink/40 text-[10px] shrink-0">
                    {idx + 1}
                  </span>
                  <span className="break-all">{line}</span>
                </div>
              )
            })}
          </code>
        </pre>
      </div>
    </div>
  )
}
