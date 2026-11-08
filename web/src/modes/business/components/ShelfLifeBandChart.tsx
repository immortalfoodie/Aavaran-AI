import React, { useState, useRef } from 'react'
import type { PackagingSpecSheet, RouteLeg } from '../types'

interface ShelfLifeBandChartProps {
  structure: PackagingSpecSheet
  targetDays: number
  routeLegs: RouteLeg[]
}

export const ShelfLifeBandChart: React.FC<ShelfLifeBandChartProps> = ({
  structure,
  targetDays,
  routeLegs,
}) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportResult, setReportResult] = useState<{
    timestamp: string
  } | null>(null)
  const shelfLifeRef = useRef<HTMLDivElement>(null)

  const handleGenerateShelfLifeReport = async () => {
    setReportLoading(true)
    await new Promise((resolve) => setTimeout(resolve, 500))
    const now = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
    setReportResult({ timestamp: now })
    setReportLoading(false)
    setTimeout(() => {
      shelfLifeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120)
  }

  // Chart coordinate space
  const width = 800
  const height = 340
  const padding = { top: 30, right: 40, bottom: 50, left: 60 }

  const chartW = width - padding.left - padding.right
  const chartH = height - padding.top - padding.bottom

  const maxDays = Math.max(targetDays * 1.35, structure.predictedShelfLifeDaysP90 * 1.15, 60)

  // Generate 50 points along the time curve
  const numPoints = 50
  const points = Array.from({ length: numPoints }, (_, i) => {
    const day = (i / (numPoints - 1)) * maxDays

    // Quality degradation follows sigmoidal / power kinetics
    // P10 reaches 0% quality at structure.predictedShelfLifeDaysP10
    // P50 reaches 0% quality at structure.predictedShelfLifeDaysP50
    // P90 reaches 0% quality at structure.predictedShelfLifeDaysP90
    const qP10 = Math.max(0, 100 * Math.pow(Math.max(0, 1 - day / structure.predictedShelfLifeDaysP10), 1.3))
    const qP50 = Math.max(0, 100 * Math.pow(Math.max(0, 1 - day / structure.predictedShelfLifeDaysP50), 1.2))
    const qP90 = Math.max(0, 100 * Math.pow(Math.max(0, 1 - day / structure.predictedShelfLifeDaysP90), 1.1))

    return { day, qP10, qP50, qP90 }
  })

  // Convert (day, q) to (x, y)
  const getX = (day: number) => padding.left + (day / maxDays) * chartW
  const getY = (q: number) => padding.top + (1 - q / 100) * chartH

  // Build SVG path for P10, P50, P90
  const lineP10 = points.map((p) => `${getX(p.day)},${getY(p.qP10)}`).join(' ')
  const lineP50 = points.map((p) => `${getX(p.day)},${getY(p.qP50)}`).join(' ')
  const lineP90 = points.map((p) => `${getX(p.day)},${getY(p.qP90)}`).join(' ')

  // Shaded polygon between P10 and P90
  const p90Coords = points.map((p) => `${getX(p.day)},${getY(p.qP90)}`)
  const p10CoordsReversed = [...points].reverse().map((p) => `${getX(p.day)},${getY(p.qP10)}`)
  const bandPolygon = [...p90Coords, ...p10CoordsReversed].join(' ')

  const targetX = getX(targetDays)

  // Journey milestones cumulative hours to days
  const legMarkers = routeLegs.map((leg, idx) => {
    const day = routeLegs.slice(0, idx + 1).reduce((sum, l) => sum + l.durationHours / 24, 0)
    return {
      name: leg.name,
      day,
      x: getX(day),
    }
  })

  const hoveredPoint = hoverIndex !== null ? points[hoverIndex] : null

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="font-mono text-xs font-bold uppercase tracking-wider bg-cyan text-ink px-2 py-0.5 inline-block mb-1 border border-ink">
            STOCHASTIC SHELF-LIFE SIMULATION · P10 TO P90 CONFIDENCE ENVELOPE
          </span>
          <h3 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
            P10–P90 Shelf-Life Degradation Band
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-3 font-mono text-xs">
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-3 bg-cyan/40 border border-ink" />
            <span className="font-bold">P10–P90 Band</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 bg-ink" />
            <span className="font-bold">P50 Expected</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 bg-coral border-dashed" />
            <span className="font-bold text-coral">Target ({targetDays}d)</span>
          </div>
        </div>
      </div>

      <p className="font-body text-xs text-ink/80">
        Calculated across dynamic supply-chain temperatures and humidity. P10 represents the conservative worst-case scenario (90% survival guarantee), while P90 represents ideal storage.
      </p>

      {/* SVG Chart */}
      <div className="relative border-3 border-ink bg-paper overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full min-w-[640px] h-auto select-none"
          onMouseLeave={() => setHoverIndex(null)}
        >
          {/* Grid lines */}
          {[0, 25, 50, 75, 100].map((level) => {
            const y = getY(level)
            return (
              <g key={level}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke="#0B0B0B"
                  strokeWidth="1"
                  strokeDasharray="3 3"
                  opacity="0.25"
                />
                <text
                  x={padding.left - 10}
                  y={y + 4}
                  textAnchor="end"
                  className="font-mono text-[11px] font-bold fill-ink"
                >
                  {level}%
                </text>
              </g>
            )
          })}

          {/* Time axis ticks */}
          {[0, 30, 60, 90, 180, 270, 365]
            .filter((d) => d <= maxDays)
            .map((day) => {
              const x = getX(day)
              return (
                <g key={day}>
                  <line
                    x1={x}
                    y1={height - padding.bottom}
                    x2={x}
                    y2={height - padding.bottom + 6}
                    stroke="#0B0B0B"
                    strokeWidth="2"
                  />
                  <text
                    x={x}
                    y={height - padding.bottom + 20}
                    textAnchor="middle"
                    className="font-mono text-[11px] font-bold fill-ink"
                  >
                    {day}d
                  </text>
                </g>
              )
            })}

          {/* Shaded P10-P90 Confidence Band */}
          <polygon
            points={bandPolygon}
            fill="#5CE1FF"
            fillOpacity="0.38"
            stroke="#0B0B0B"
            strokeWidth="1.5"
          />

          {/* P10 Lower Bound Line */}
          <polyline
            points={lineP10}
            fill="none"
            stroke="#0B0B0B"
            strokeWidth="2"
            strokeDasharray="4 2"
          />

          {/* P90 Upper Bound Line */}
          <polyline
            points={lineP90}
            fill="none"
            stroke="#0B0B0B"
            strokeWidth="2"
            strokeDasharray="4 2"
          />

          {/* P50 Median Line */}
          <polyline points={lineP50} fill="none" stroke="#0B0B0B" strokeWidth="3.5" />

          {/* Target Shelf Life Vertical Marker */}
          {targetX <= width - padding.right && (
            <g>
              <line
                x1={targetX}
                y1={padding.top}
                x2={targetX}
                y2={height - padding.bottom}
                stroke="#FF6B52"
                strokeWidth="2.5"
                strokeDasharray="5 3"
              />
              <rect
                x={targetX - 45}
                y={padding.top + 5}
                width="90"
                height="22"
                fill="#FF6B52"
                stroke="#0B0B0B"
                strokeWidth="2"
              />
              <text
                x={targetX}
                y={padding.top + 20}
                textAnchor="middle"
                className="font-display text-[10px] font-bold fill-ink uppercase"
              >
                TARGET {targetDays}D
              </text>
            </g>
          )}

          {/* Multi-Leg Supply Chain Journey Milestones */}
          {legMarkers.map((leg, idx) => {
            if (leg.x > width - padding.right) return null
            return (
              <g key={idx} opacity="0.8">
                <line
                  x1={leg.x}
                  y1={height - padding.bottom - 40}
                  x2={leg.x}
                  y2={height - padding.bottom}
                  stroke="#0B0B0B"
                  strokeWidth="1.5"
                  strokeDasharray="2 2"
                />
                <circle cx={leg.x} cy={height - padding.bottom} r="3" fill="#0B0B0B" />
              </g>
            )
          })}

          {/* Interactive Mouse Hover Overlay Columns */}
          {points.map((p, idx) => {
            const x = getX(p.day)
            const colWidth = chartW / numPoints
            return (
              <rect
                key={idx}
                x={x - colWidth / 2}
                y={padding.top}
                width={colWidth}
                height={chartH}
                fill="transparent"
                className="cursor-crosshair"
                onMouseEnter={() => setHoverIndex(idx)}
              />
            )
          })}

          {/* Hover Indicator Crosshair */}
          {hoveredPoint && (
            <g>
              <line
                x1={getX(hoveredPoint.day)}
                y1={padding.top}
                x2={getX(hoveredPoint.day)}
                y2={height - padding.bottom}
                stroke="#0B0B0B"
                strokeWidth="1.5"
              />
              <circle
                cx={getX(hoveredPoint.day)}
                cy={getY(hoveredPoint.qP50)}
                r="5"
                fill="#FFE500"
                stroke="#0B0B0B"
                strokeWidth="2"
              />
            </g>
          )}

          {/* Chart Axes Borders */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={height - padding.bottom}
            stroke="#0B0B0B"
            strokeWidth="3"
          />
          <line
            x1={padding.left}
            y1={height - padding.bottom}
            x2={width - padding.right}
            y2={height - padding.bottom}
            stroke="#0B0B0B"
            strokeWidth="3"
          />

          {/* Axis Labels */}
          <text
            x={width / 2}
            y={height - 12}
            textAnchor="middle"
            className="font-display text-xs uppercase fill-ink"
          >
            Commercial Storage Timeline (Days)
          </text>
          <text
            x={-height / 2 + 10}
            y={18}
            transform="rotate(-90)"
            textAnchor="middle"
            className="font-display text-xs uppercase fill-ink"
          >
            Product Quality / Moisture Retention (%)
          </text>
        </svg>

        {/* Hover Readout Box */}
        {hoveredPoint && (
          <div className="absolute top-3 right-3 bg-paper border-2 border-ink p-2 shadow-[3px_3px_0_var(--ink)] font-mono text-xs space-y-0.5 z-10">
            <div className="font-display text-[11px] uppercase border-b border-ink pb-1">
              DAY {Math.round(hoveredPoint.day)}
            </div>
            <div>
              P90: <span className="font-bold">{hoveredPoint.qP90.toFixed(1)}%</span>
            </div>
            <div>
              P50: <span className="font-bold text-ink">{hoveredPoint.qP50.toFixed(1)}%</span>
            </div>
            <div>
              P10: <span className="font-bold text-coral">{hoveredPoint.qP10.toFixed(1)}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Numerical Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
        <div className="p-3 border-2 border-ink bg-paper">
          <span className="font-mono text-[10px] text-ink/70 block uppercase">
            P10 CONSERVATIVE (WORST CASE)
          </span>
          <span className="font-display text-xl text-ink">
            {structure.predictedShelfLifeDaysP10} DAYS
          </span>
          <p className="font-body text-[11px] text-ink/80 mt-1">
            {structure.predictedShelfLifeDaysP10 >= targetDays ? (
              <span className="text-ink font-bold bg-lime px-1">✓ MEETS TARGET (90% CONFIDENCE)</span>
            ) : (
              <span className="text-ink font-bold bg-coral px-1">⚠ RISK OF PREMATURE SPOILAGE</span>
            )}
          </p>
        </div>

        <div className="p-3 border-2 border-ink bg-cyan/20 border-cyan">
          <span className="font-mono text-[10px] text-ink/70 block uppercase font-bold">
            P50 MEDIAN EXPECTED
          </span>
          <span className="font-display text-xl text-ink">
            {structure.predictedShelfLifeDaysP50} DAYS
          </span>
          <p className="font-body text-[11px] text-ink/80 mt-1">
            Safety factor of 0.75 already integrated into numerical boundary.
          </p>
        </div>

        <div className="p-3 border-2 border-ink bg-paper">
          <span className="font-mono text-[10px] text-ink/70 block uppercase">
            P90 OPTIMISTIC (CONTROLLED WAREHOUSE)
          </span>
          <span className="font-display text-xl text-ink">
            {structure.predictedShelfLifeDaysP90} DAYS
          </span>
          <p className="font-body text-[11px] text-ink/80 mt-1">
            Cold storage buffer allows product longevity extension.
          </p>
        </div>
      </div>

      {/* Action Button: Generate Shelf Life Report */}
      <div className="pt-2 flex justify-end">
        <button
          type="button"
          disabled={reportLoading}
          onClick={handleGenerateShelfLifeReport}
          style={
            reportLoading
              ? {
                  animation: 'rfq-pulse 1s infinite ease-in-out',
                  pointerEvents: 'none',
                }
              : undefined
          }
          className={`font-display text-xs uppercase px-5 py-2.5 border-2 border-ink flex items-center gap-1.5 transition-all ${
            reportLoading
              ? 'bg-grey text-ink cursor-not-allowed shadow-none'
              : 'bg-yellow text-ink hover:bg-yellow/80 shadow-[3px_3px_0_var(--ink)] cursor-pointer'
          }`}
        >
          {reportLoading ? (
            <span>⚡ GENERATING SHELF LIFE REPORT…</span>
          ) : (
            <>
              <span>📊</span>
              <span>Generate Shelf Life Report</span>
            </>
          )}
        </button>
      </div>

      {/* Shelf Life Report Result Container with Visual Anchor */}
      {reportResult && (
        <div ref={shelfLifeRef} className="rfq-result-section">
          <div className="rfq-section-header">
            <span className="font-display font-black text-sm sm:text-base">
              ✓ SHELF LIFE REPORT GENERATED — {structure.name}
            </span>
            <span className="font-mono text-xs normal-case opacity-90">
              Generated {reportResult.timestamp}
            </span>
          </div>
          <div className="mt-4 p-5 border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b-2 border-ink pb-3">
              <div>
                <span className="font-mono text-xs font-bold uppercase bg-yellow text-ink px-2 py-0.5 border border-ink">
                  KINETIC STOCHASTIC SIMULATION AUDIT
                </span>
                <h4 className="font-display text-lg uppercase text-ink mt-1 m-0">
                  Comprehensive Shelf Life Longevity Dossier
                </h4>
              </div>
              <span className="font-mono text-xs font-bold bg-paper border-2 border-ink px-2 py-1">
                FSSAI LAB CONFORMITY
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div className="p-3 border-2 border-ink bg-paper">
                <span className="font-mono text-ink/70 uppercase block">Target Shelf Life</span>
                <span className="font-display text-base text-ink">{targetDays} Days</span>
              </div>
              <div className="p-3 border-2 border-ink bg-paper">
                <span className="font-mono text-ink/70 uppercase block">P10 Conservative</span>
                <span className="font-display text-base text-coral">{structure.predictedShelfLifeDaysP10} Days</span>
              </div>
              <div className="p-3 border-2 border-ink bg-paper">
                <span className="font-mono text-ink/70 uppercase block">P50 Expected</span>
                <span className="font-display text-base text-ink font-bold">{structure.predictedShelfLifeDaysP50} Days</span>
              </div>
              <div className="p-3 border-2 border-ink bg-paper">
                <span className="font-mono text-ink/70 uppercase block">P90 Optimistic</span>
                <span className="font-display text-base text-lime-800">{structure.predictedShelfLifeDaysP90} Days</span>
              </div>
            </div>

            <div className="p-3 border-2 border-ink bg-grey/20 font-mono text-xs space-y-1">
              <div><strong>Primary Barrier Permeation:</strong> WVTR {structure.wvtrGPerM2Day} g/m²·day | OTR {structure.otrCcPerM2Day} cc/m²·day</div>
              <div><strong>Limiting Degradation Mode:</strong> {structure.isMoistureSensitive ? 'Moisture Uptake / Water Activity (aw) Drift' : 'Oxygen Oxidation / Lipid Rancidity'}</div>
              <div><strong>Integrated Safety Margin:</strong> {Math.max(0, Math.round(((structure.predictedShelfLifeDaysP50 - targetDays) / targetDays) * 100))}% over commercial distribution requirement</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
