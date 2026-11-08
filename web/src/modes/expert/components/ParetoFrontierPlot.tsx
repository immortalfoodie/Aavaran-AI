import React, { useState, useRef } from 'react'
import type { CandidateStructurePoint } from '../types'

interface ParetoFrontierPlotProps {
  candidates: CandidateStructurePoint[]
  onSelectCandidate?: (candidate: CandidateStructurePoint) => void
}

export const ParetoFrontierPlot: React.FC<ParetoFrontierPlotProps> = ({
  candidates,
  onSelectCandidate,
}) => {
  const [hoveredCandidate, setHoveredCandidate] = useState<CandidateStructurePoint | null>(null)
  const [computing, setComputing] = useState(false)
  const [paretoResult, setParetoResult] = useState<{
    timestamp: string
    optimalCount: number
    dominatedCount: number
  } | null>(null)
  const paretoRef = useRef<HTMLDivElement>(null)

  const width = 760
  const height = 360
  const padding = { top: 30, right: 40, bottom: 50, left: 60 }

  const chartW = width - padding.left - padding.right
  const chartH = height - padding.top - padding.bottom

  const minCost = 0.8
  const maxCost = 4.2
  const minShelfLife = 40
  const maxShelfLife = 400

  const getX = (cost: number) =>
    padding.left + ((cost - minCost) / (maxCost - minCost)) * chartW
  const getY = (days: number) =>
    padding.top + (1 - (days - minShelfLife) / (maxShelfLife - minShelfLife)) * chartH

  // Filter and sort Pareto optimal points by cost ascending to draw the frontier line
  const paretoPoints = candidates
    .filter((c) => c.isParetoOptimal)
    .sort((a, b) => a.costPerPackInr - b.costPerPackInr)

  const frontierPath = paretoPoints
    .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(p.costPerPackInr)} ${getY(p.shelfLifeDays)}`)
    .join(' ')

  const handleComputeParetoFrontier = async () => {
    setComputing(true)
    await new Promise((resolve) => setTimeout(resolve, 500))
    const now = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
    setParetoResult({
      timestamp: now,
      optimalCount: paretoPoints.length,
      dominatedCount: candidates.length - paretoPoints.length,
    })
    setComputing(false)
    setTimeout(() => {
      paretoRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120)
  }

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
              MULTI-OBJECTIVE OPTIMIZATION
            </span>
            <span className="font-mono text-xs font-bold text-ink/70">
              NON-DOMINATED SOLUTION ENVELOPE
            </span>
          </div>
          <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            05 · Pareto Frontier (Cost vs Shelf Life vs Circularity)
          </h3>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Structures plotted across production cost, shelf-life performance, and recyclability index. The continuous bold line demarcates the non-dominated Pareto frontier.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4 font-mono text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 bg-lime border border-ink inline-block" />
            <span>High Circularity (Cat I/II)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 bg-coral border border-ink inline-block" />
            <span>Multi-Layer (Cat III)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 bg-violet border-2 border-violet inline-block" />
            <span className="font-bold text-ink">Pareto Frontier</span>
          </div>
        </div>
      </div>

      {/* Scatter Plot SVG */}
      <div className="relative border-3 border-ink bg-paper overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full min-w-[620px] h-auto select-none"
          onMouseLeave={() => setHoveredCandidate(null)}
        >
          {/* Horizontal Grid (Shelf Life) */}
          {[100, 200, 300, 400].map((days, idx) => {
            const y = getY(days)
            return (
              <g key={idx}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke="#0B0B0B"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                  opacity="0.2"
                />
                <text
                  x={padding.left - 8}
                  y={y + 4}
                  textAnchor="end"
                  className="font-mono text-[10px] font-bold fill-ink"
                >
                  {days}d
                </text>
              </g>
            )
          })}

          {/* Vertical Grid (Cost) */}
          {[1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0].map((cost, idx) => {
            const x = getX(cost)
            return (
              <g key={idx}>
                <line
                  x1={x}
                  y1={padding.top}
                  x2={x}
                  y2={height - padding.bottom}
                  stroke="#0B0B0B"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                  opacity="0.2"
                />
                <text
                  x={x}
                  y={height - padding.bottom + 18}
                  textAnchor="middle"
                  className="font-mono text-[10px] font-bold fill-ink"
                >
                  ₹{cost.toFixed(1)}
                </text>
              </g>
            )
          })}

          {/* Pareto Frontier Line */}
          <path
            d={frontierPath}
            fill="none"
            stroke="#C3A6FF"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Candidate Points */}
          {candidates.map((cand) => {
            const cx = getX(cand.costPerPackInr)
            const cy = getY(cand.shelfLifeDays)
            const isHovered = hoveredCandidate?.id === cand.id

            // Bubble color based on recyclability
            const bubbleFill =
              cand.recyclabilityScorePct >= 80
                ? '#C9FF3D' // Lime (High circularity)
                : cand.recyclabilityScorePct >= 50
                ? '#FFE500' // Yellow
                : '#FF6B52' // Coral (MLP)

            const radius = 6 + (cand.recyclabilityScorePct / 100) * 5

            return (
              <g
                key={cand.id}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredCandidate(cand)}
                onClick={() => onSelectCandidate && onSelectCandidate(cand)}
              >
                {/* Pareto aura ring */}
                {cand.isParetoOptimal && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={radius + 4}
                    fill="none"
                    stroke="#0B0B0B"
                    strokeWidth="1.5"
                    strokeDasharray="2 2"
                  />
                )}

                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? radius + 3 : radius}
                  fill={bubbleFill}
                  stroke="#0B0B0B"
                  strokeWidth={isHovered ? '3' : '2'}
                  className="transition-all"
                />

                {/* Point Label */}
                <text
                  x={cx + radius + 4}
                  y={cy + 3}
                  className={`font-mono text-[10px] ${
                    cand.isParetoOptimal ? 'font-bold fill-ink' : 'fill-ink/60'
                  }`}
                >
                  {cand.name.split('/')[0].trim()}
                </text>
              </g>
            )
          })}

          {/* Axes */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={height - padding.bottom}
            stroke="#0B0B0B"
            strokeWidth="2.5"
          />
          <line
            x1={padding.left}
            y1={height - padding.bottom}
            x2={width - padding.right}
            y2={height - padding.bottom}
            stroke="#0B0B0B"
            strokeWidth="2.5"
          />

          {/* Labels */}
          <text
            x={width / 2}
            y={height - 10}
            textAnchor="middle"
            className="font-display text-xs uppercase fill-ink"
          >
            Indicative Pack Cost (₹ / unit)
          </text>
          <text
            x={-height / 2 + 10}
            y={16}
            transform="rotate(-90)"
            textAnchor="middle"
            className="font-display text-xs uppercase fill-ink"
          >
            Predicted Shelf Life (Days)
          </text>
        </svg>

        {/* Hover Inspector Tooltip */}
        {hoveredCandidate && (
          <div className="absolute top-3 right-3 bg-paper border-2 border-ink p-3 shadow-[4px_4px_0_var(--ink)] font-mono text-xs space-y-1 z-10 max-w-sm">
            <div className="flex items-center justify-between border-b border-ink pb-1">
              <span className="font-display text-xs uppercase text-ink">
                {hoveredCandidate.name}
              </span>
              {hoveredCandidate.isParetoOptimal && (
                <span className="bg-violet text-ink font-mono text-[10px] px-1 font-bold border border-ink">
                  PARETO OPTIMAL
                </span>
              )}
            </div>
            <div>
              Layer Stack: <span className="font-bold">{hoveredCandidate.layerStack}</span>
            </div>
            <div>
              Cost: <span className="font-bold text-ink">₹{hoveredCandidate.costPerPackInr.toFixed(2)}</span>
            </div>
            <div>
              Shelf Life: <span className="font-bold text-ink">{hoveredCandidate.shelfLifeDays} days</span>
            </div>
            <div>
              Recyclability Index:{' '}
              <span className="font-bold text-lime-800">
                {hoveredCandidate.recyclabilityScorePct}% ({hoveredCandidate.eprCategory})
              </span>
            </div>
            <div>
              Gauge: <span className="font-bold">{hoveredCandidate.compositeThicknessUm} µm</span>
            </div>
          </div>
        )}
      </div>

      <div className="p-3 border-2 border-ink bg-violet/15 text-xs font-mono text-ink/80 flex items-center justify-between">
        <span>FRONTIER INSIGHT: <strong>25u MDO-PE / 45u PE-EVOH-PE</strong></span>
        <span>Reaches 260 days shelf life while retaining 94% RecyClass recyclability score</span>
      </div>

      {/* Action Button: Compute Pareto Frontier */}
      <div className="pt-2 flex justify-end">
        <button
          type="button"
          disabled={computing}
          onClick={handleComputeParetoFrontier}
          style={
            computing
              ? {
                  animation: 'rfq-pulse 1s infinite ease-in-out',
                  pointerEvents: 'none',
                }
              : undefined
          }
          className={`font-display text-xs uppercase px-5 py-2.5 border-2 border-ink flex items-center gap-1.5 transition-all ${
            computing
              ? 'bg-grey text-ink cursor-not-allowed shadow-none'
              : 'bg-yellow text-ink hover:bg-yellow/80 shadow-[3px_3px_0_var(--ink)] cursor-pointer'
          }`}
        >
          {computing ? (
            <span>⚡ COMPUTING PARETO FRONTIER…</span>
          ) : (
            <>
              <span>🔬</span>
              <span>Compute Pareto Frontier</span>
            </>
          )}
        </button>
      </div>

      {/* Pareto Result Section with Visual Anchor */}
      {paretoResult && (
        <div ref={paretoRef} className="rfq-result-section">
          <div className="rfq-section-header">
            <span className="font-display font-black text-sm sm:text-base">
              ✓ PARETO FRONTIER COMPUTED — Non-Dominated Solution Envelope
            </span>
            <span className="font-mono text-xs normal-case opacity-90">
              Generated {paretoResult.timestamp}
            </span>
          </div>
          <div className="mt-4 p-5 border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b-2 border-ink pb-3">
              <div>
                <span className="font-mono text-xs font-bold uppercase bg-violet text-ink px-2 py-0.5 border border-ink">
                  MULTI-DIMENSIONAL CONVEX HULL
                </span>
                <h4 className="font-display text-lg uppercase text-ink mt-1 m-0">
                  Pareto-Optimal Candidate Structures
                </h4>
              </div>
              <span className="font-mono text-xs font-bold bg-paper border-2 border-ink px-2 py-1">
                {paretoResult.optimalCount} NON-DOMINATED / {candidates.length} TOTAL
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {paretoPoints.map((p) => (
                <div key={p.id} className="p-3 border-2 border-ink bg-paper space-y-1 text-xs">
                  <div className="font-display uppercase text-ink truncate">{p.name}</div>
                  <div className="font-mono text-[11px] text-ink/70">{p.layerStack}</div>
                  <div className="flex items-center justify-between pt-1 border-t border-ink/20 font-mono">
                    <span className="font-bold text-ink">₹{p.costPerPackInr.toFixed(2)}/pk</span>
                    <span className="text-lime-800 font-bold">{p.shelfLifeDays}d</span>
                    <span className="bg-lime/30 px-1">{p.recyclabilityScorePct}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
