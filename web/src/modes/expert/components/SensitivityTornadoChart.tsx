import React, { useState } from 'react'
import type { SensitivityItem } from '../types'

interface SensitivityTornadoChartProps {
  items?: SensitivityItem[]
}

const PARAM_LABELS: Record<string, { label: string; symbol: string }> = {
  storage_temperature: { label: 'Ambient Storage Temperature', symbol: 'T_amb' },
  initial_moisture: { label: 'Initial Product Moisture', symbol: 'm_0' },
  storage_rh: { label: 'Ambient Relative Humidity', symbol: 'RH_amb' },
  pack_area: { label: 'Exposed Pack Surface Area', symbol: 'A_pack' },
  respiration_rate: { label: 'Commodity Respiration Rate', symbol: 'R_O2' },
  relative_humidity: { label: 'Ambient Relative Humidity', symbol: 'RH_amb' },
  water_activity: { label: 'Water Activity', symbol: 'a_w' },
  pH: { label: 'Commodity pH', symbol: 'pH' },
}

export const SensitivityTornadoChart: React.FC<SensitivityTornadoChartProps> = ({ items = [] }) => {
  const [hoveredParam, setHoveredParam] = useState<SensitivityItem | null>(null)

  if (!items || items.length === 0) {
    return (
      <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
                GLOBAL VARIANCE DECOMPOSITION
              </span>
            </div>
            <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
              03 · Sensitivity Tornado Chart
            </h3>
          </div>
        </div>
        <div className="p-8 text-center border-2 border-ink bg-grey/10 font-mono text-sm text-ink/80">
          Run a recommendation to see sensitivity data.
        </div>
      </div>
    )
  }

  // Sort descending by variance reduction percentage
  const sortedItems = [...items].sort((a, b) => b.variance_reduction_pct - a.variance_reduction_pct)
  const totalVariancePct = sortedItems.reduce((acc, curr) => acc + curr.variance_reduction_pct, 0)

  const width = 760
  const height = Math.max(260, 50 + sortedItems.length * 48)
  const padding = { top: 30, right: 90, bottom: 40, left: 240 }
  const chartW = width - padding.left - padding.right
  const chartH = height - padding.top - padding.bottom
  const rowHeight = chartH / sortedItems.length

  const maxPct = Math.max(...sortedItems.map((i) => i.variance_reduction_pct), 50)

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
              VARIANCE DECOMPOSITION (UNCERTAINTY.PY)
            </span>
            <span className="font-mono text-xs font-bold text-ink/70">
              TOTAL EXPLAINED VARIANCE: {Math.round(totalVariancePct)}%
            </span>
          </div>
          <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            03 · Sensitivity Tornado Chart
          </h3>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Parameters ranked strictly by their variance reduction on predicted commercial shelf life. Real engine output computed from deterministic VoI analysis.
          </p>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 bg-coral border border-ink inline-block" />
            <span>Curtailment Driver (−)</span>
          </div>
        </div>
      </div>

      {/* Tornado SVG */}
      <div className="relative border-3 border-ink bg-paper overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full min-w-[620px] h-auto select-none"
          onMouseLeave={() => setHoveredParam(null)}
        >
          {/* Vertical Zero Baseline */}
          <line
            x1={padding.left}
            y1={padding.top - 10}
            x2={padding.left}
            y2={height - padding.bottom}
            stroke="#0B0B0B"
            strokeWidth="2.5"
          />

          {/* Grid lines */}
          {[10, 20, 30, 40, 50].map((val) => {
            if (val > maxPct + 5) return null
            const x = padding.left + (val / maxPct) * chartW
            return (
              <g key={val}>
                <line
                  x1={x}
                  y1={padding.top}
                  x2={x}
                  y2={height - padding.bottom}
                  stroke="#0B0B0B"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                  opacity="0.25"
                />
                <text
                  x={x}
                  y={height - padding.bottom + 18}
                  textAnchor="middle"
                  className="font-mono text-[10px] font-bold fill-ink"
                >
                  {val}%
                </text>
              </g>
            )
          })}

          <text
            x={padding.left}
            y={height - padding.bottom + 18}
            textAnchor="middle"
            className="font-mono text-[10px] font-bold fill-ink"
          >
            0%
          </text>

          {/* Tornado Rows */}
          {sortedItems.map((item, idx) => {
            const y = padding.top + idx * rowHeight + rowHeight * 0.15
            const barH = Math.max(16, rowHeight * 0.65)
            const barW = Math.max(4, (item.variance_reduction_pct / maxPct) * chartW)
            const isHovered = hoveredParam?.parameter === item.parameter

            const meta = PARAM_LABELS[item.parameter] || {
              label: item.parameter.replace(/_/g, ' ').toUpperCase(),
              symbol: item.parameter,
            }

            return (
              <g
                key={item.parameter}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredParam(item)}
              >
                {/* Row Hover Background */}
                {isHovered && (
                  <rect
                    x={padding.left - 230}
                    y={y - 2}
                    width={width - padding.right + 230}
                    height={barH + 4}
                    fill="#C3A6FF"
                    fillOpacity="0.2"
                  />
                )}

                {/* Parameter Label */}
                <text
                  x={padding.left - 12}
                  y={y + barH * 0.7}
                  textAnchor="end"
                  className={`font-display text-[11px] uppercase ${
                    isHovered ? 'fill-violet font-bold' : 'fill-ink'
                  }`}
                >
                  #{idx + 1} {meta.label}
                </text>

                {/* Tornado Bar */}
                <rect
                  x={padding.left}
                  y={y}
                  width={barW}
                  height={barH}
                  fill={idx === 0 ? '#FF6B52' : idx === 1 ? '#FFAA48' : '#C3A6FF'}
                  stroke="#0B0B0B"
                  strokeWidth="1.5"
                />

                {/* Value on the right */}
                <text
                  x={padding.left + barW + 8}
                  y={y + barH * 0.7}
                  className="font-mono text-[11px] font-bold fill-ink"
                >
                  {item.variance_reduction_pct.toFixed(1)}%
                </text>
              </g>
            )
          })}
        </svg>

        {/* Hover Inspector Tooltip */}
        {hoveredParam && (
          <div className="absolute top-3 right-3 bg-paper border-2 border-ink p-2.5 shadow-[3px_3px_0_var(--ink)] font-mono text-xs space-y-1 z-10 max-w-xs">
            <div className="font-display text-xs uppercase border-b border-ink pb-1">
              {PARAM_LABELS[hoveredParam.parameter]?.label || hoveredParam.parameter}
            </div>
            <div>
              Variance Reduction:{' '}
              <span className="font-bold text-coral">
                {hoveredParam.variance_reduction_pct.toFixed(1)}%
              </span>
            </div>
            <div>
              Impact Direction:{' '}
              <span className="font-bold">{hoveredParam.direction}</span>
            </div>
          </div>
        )}
      </div>

      <div className="p-3 border-2 border-ink bg-grey/25 text-xs font-mono text-ink/80 flex items-center justify-between">
        <span>
          PRIMARY UNCERTAINTY LEVER: <strong>{PARAM_LABELS[sortedItems[0]?.parameter]?.label || sortedItems[0]?.parameter}</strong>
        </span>
        <span>
          Variance Reduction: <strong>{sortedItems[0]?.variance_reduction_pct.toFixed(1)}%</strong>
        </span>
      </div>
    </div>
  )
}
