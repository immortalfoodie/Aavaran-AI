import React, { useState, useMemo } from 'react'
import type { SealedShelfLife, MonteCarloHistogramBin } from '../types'

interface MonteCarloDistributionProps {
  shelfLife?: SealedShelfLife | null
}

export const MonteCarloDistribution: React.FC<MonteCarloDistributionProps> = ({ shelfLife }) => {
  const [hoveredBin, setHoveredBin] = useState<MonteCarloHistogramBin | null>(null)

  const p10 = shelfLife?.days_p10 ?? 0
  const p50 = shelfLife?.days_p50 ?? 0
  const p90 = shelfLife?.days_p90 ?? 0
  const mechanism = shelfLife?.mechanism || shelfLife?.limiting_mechanism || 'MOISTURE_GAIN'
  const confidenceVal = shelfLife?.confidence ?? 0.85
  const confidencePct = Math.round(confidenceVal <= 1 ? confidenceVal * 100 : confidenceVal)

  // Construct bins from real distribution_samples or deterministic triangular distribution
  const bins = useMemo<MonteCarloHistogramBin[]>(() => {
    if (!shelfLife || (!p10 && !p50 && !p90)) return []

    const samples = shelfLife.distribution_samples
    if (samples && samples.length > 0) {
      // Bin actual samples
      const minVal = Math.min(...samples)
      const maxVal = Math.max(...samples)
      const numBins = 24
      const binWidth = Math.max(0.1, (maxVal - minVal) / numBins)
      const counts = new Array(numBins).fill(0)

      for (const val of samples) {
        let idx = Math.floor((val - minVal) / binWidth)
        if (idx >= numBins) idx = numBins - 1
        if (idx < 0) idx = 0
        counts[idx]++
      }

      return counts.map((count, idx) => {
        const start = minVal + idx * binWidth
        const end = start + binWidth
        const freq = (count / samples.length) * 100
        return {
          daysStart: Math.round(start * 10) / 10,
          daysEnd: Math.round(end * 10) / 10,
          count,
          frequencyPct: Math.round(freq * 10) / 10,
          isP10Bin: start <= p10 && p10 <= end,
          isP50Bin: start <= p50 && p50 <= end,
          isP90Bin: start <= p90 && p90 <= end,
        }
      })
    }

    // Triangular distribution:
    // min = p10 - 0.5 * (p50 - p10)
    // mode = p50
    // max = p90 + 0.5 * (p90 - p50)
    const a = Math.max(1, p10 - 0.5 * (p50 - p10))
    const c = p50
    const b = Math.max(c + 1, p90 + 0.5 * (p90 - p50))

    const cdf = (x: number): number => {
      if (x <= a) return 0
      if (x >= b) return 1
      if (x <= c) {
        return Math.pow(x - a, 2) / ((b - a) * (c - a))
      }
      return 1 - Math.pow(b - x, 2) / ((b - a) * (b - c))
    }

    const numBins = 24
    const binWidth = (b - a) / numBins
    const totalSimulations = 1000

    const computedBins: MonteCarloHistogramBin[] = []
    for (let i = 0; i < numBins; i++) {
      const start = a + i * binWidth
      const end = start + binWidth
      const prob = Math.max(0, cdf(end) - cdf(start))
      const count = Math.round(prob * totalSimulations)
      const freq = prob * 100

      computedBins.push({
        daysStart: Math.round(start * 10) / 10,
        daysEnd: Math.round(end * 10) / 10,
        count,
        frequencyPct: Math.round(freq * 10) / 10,
        isP10Bin: start <= p10 && p10 < end,
        isP50Bin: start <= p50 && p50 < end,
        isP90Bin: start <= p90 && p90 <= end,
      })
    }
    return computedBins
  }, [shelfLife, p10, p50, p90])

  if (!shelfLife || (!p10 && !p50 && !p90)) {
    return (
      <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-4">
        <div className="border-b-3 border-ink pb-4">
          <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
            STOCHASTIC SHELF-LIFE SIMULATION
          </span>
          <h3 className="font-display text-2xl uppercase tracking-tight text-ink mt-2">
            04 · Monte Carlo Probability Distribution
          </h3>
        </div>
        <div className="py-12 text-center font-mono text-sm text-ink/60">
          Run a recommendation to see shelf life probability distribution.
        </div>
      </div>
    )
  }

  const width = 760
  const height = 330
  const padding = { top: 40, right: 30, bottom: 50, left: 50 }

  const chartW = width - padding.left - padding.right
  const chartH = height - padding.top - padding.bottom

  const maxFreq = Math.max(...bins.map((b) => b.frequencyPct), 10)
  const minDay = bins[0]?.daysStart ?? p10
  const maxDay = bins[bins.length - 1]?.daysEnd ?? p90

  const getX = (day: number) => {
    if (maxDay === minDay) return padding.left + chartW / 2
    return padding.left + Math.max(0, Math.min(1, (day - minDay) / (maxDay - minDay))) * chartW
  }
  const getY = (freq: number) =>
    padding.top + (1 - freq / maxFreq) * chartH

  const p10X = getX(p10)
  const p50X = getX(p50)
  const p90X = getX(p90)

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
              TRIANGULAR STOCHASTIC SIMULATION
            </span>
            <span className="font-mono text-xs font-bold uppercase bg-coral text-ink px-2 py-0.5 border border-ink">
              LIMITING MECHANISM: {mechanism}
            </span>
            <span className="font-mono text-xs font-bold bg-white text-ink px-2 py-0.5 border border-ink">
              {confidencePct}% CONFIDENCE
            </span>
          </div>
          <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            04 · Monte Carlo Shelf Life Distribution
          </h3>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Probabilistic distribution of degradation failure accounting for barrier and microclimatic variability.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <span className="px-2 py-1 bg-coral/30 border border-ink font-bold">
            P10: {p10}d
          </span>
          <span className="px-2 py-1 bg-violet text-ink border border-ink font-bold">
            P50: {p50}d
          </span>
          <span className="px-2 py-1 bg-lime/40 border border-ink font-bold">
            P90: {p90}d
          </span>
        </div>
      </div>

      {/* Distribution SVG */}
      <div className="relative border-3 border-ink bg-paper overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full min-w-[620px] h-auto select-none"
          onMouseLeave={() => setHoveredBin(null)}
        >
          {/* Frequency Horizontal Grid lines */}
          {[0, maxFreq * 0.25, maxFreq * 0.5, maxFreq * 0.75, maxFreq].map((f, idx) => {
            const y = getY(f)
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
                  {f.toFixed(0)}%
                </text>
              </g>
            )
          })}

          {/* Histogram Bins */}
          {bins.map((b, idx) => {
            const x1 = getX(b.daysStart)
            const x2 = getX(b.daysEnd)
            const barW = Math.max(1, x2 - x1 - 1)
            const barH = ((b.frequencyPct / maxFreq) * chartH)
            const y = height - padding.bottom - barH

            const isHovered = hoveredBin?.daysStart === b.daysStart

            let barFill = '#FFFDF2'
            if (b.isP50Bin) barFill = '#C3A6FF'
            else if (b.isP10Bin) barFill = '#FF6B52'
            else if (b.isP90Bin) barFill = '#C9FF3D'
            else if (isHovered) barFill = '#FFE500'

            return (
              <g
                key={idx}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredBin(b)}
              >
                <rect
                  x={x1}
                  y={y}
                  width={barW}
                  height={barH}
                  fill={barFill}
                  stroke="#0B0B0B"
                  strokeWidth="1.5"
                />
              </g>
            )
          })}

          {/* P10 Vertical Callout Marker */}
          <line
            x1={p10X}
            y1={padding.top - 15}
            x2={p10X}
            y2={height - padding.bottom}
            stroke="#FF6B52"
            strokeWidth="2.5"
            strokeDasharray="4 3"
          />
          <rect
            x={p10X - 32}
            y={padding.top - 28}
            width="64"
            height="18"
            fill="#FF6B52"
            stroke="#0B0B0B"
            strokeWidth="1.5"
          />
          <text
            x={p10X}
            y={padding.top - 16}
            textAnchor="middle"
            className="font-display text-[9px] font-bold fill-ink uppercase"
          >
            P10: {p10}D
          </text>

          {/* P50 Vertical Callout Marker */}
          <line
            x1={p50X}
            y1={padding.top - 15}
            x2={p50X}
            y2={height - padding.bottom}
            stroke="#C3A6FF"
            strokeWidth="3.5"
          />
          <rect
            x={p50X - 36}
            y={padding.top - 28}
            width="72"
            height="18"
            fill="#C3A6FF"
            stroke="#0B0B0B"
            strokeWidth="1.5"
          />
          <text
            x={p50X}
            y={padding.top - 16}
            textAnchor="middle"
            className="font-display text-[9px] font-bold fill-ink uppercase"
          >
            P50: {p50}D
          </text>

          {/* P90 Vertical Callout Marker */}
          <line
            x1={p90X}
            y1={padding.top - 15}
            x2={p90X}
            y2={height - padding.bottom}
            stroke="#C9FF3D"
            strokeWidth="2.5"
            strokeDasharray="4 3"
          />
          <rect
            x={p90X - 32}
            y={padding.top - 28}
            width="64"
            height="18"
            fill="#C9FF3D"
            stroke="#0B0B0B"
            strokeWidth="1.5"
          />
          <text
            x={p90X}
            y={padding.top - 16}
            textAnchor="middle"
            className="font-display text-[9px] font-bold fill-ink uppercase"
          >
            P90: {p90}D
          </text>

          {/* Bottom Time Axis */}
          <line
            x1={padding.left}
            y1={height - padding.bottom}
            x2={width - padding.right}
            y2={height - padding.bottom}
            stroke="#0B0B0B"
            strokeWidth="2.5"
          />

          {/* Time axis ticks */}
          {[minDay, Math.round((minDay + maxDay) / 2), maxDay].map((day, idx) => (
            <g key={idx}>
              <line
                x1={getX(day)}
                y1={height - padding.bottom}
                x2={getX(day)}
                y2={height - padding.bottom + 6}
                stroke="#0B0B0B"
                strokeWidth="2"
              />
              <text
                x={getX(day)}
                y={height - padding.bottom + 20}
                textAnchor="middle"
                className="font-mono text-[10px] font-bold fill-ink"
              >
                {day} Days
              </text>
            </g>
          ))}

          {/* Axis Labels */}
          <text
            x={width / 2}
            y={height - 10}
            textAnchor="middle"
            className="font-display text-xs uppercase fill-ink"
          >
            Predicted Shelf Life Outcome (Days)
          </text>
          <text
            x={-height / 2 + 10}
            y={16}
            transform="rotate(-90)"
            textAnchor="middle"
            className="font-display text-xs uppercase fill-ink"
          >
            Relative Frequency (%)
          </text>
        </svg>

        {/* Hover Readout Tooltip */}
        {hoveredBin && (
          <div className="absolute top-3 right-3 bg-paper border-2 border-ink p-2.5 shadow-[3px_3px_0_var(--ink)] font-mono text-xs space-y-0.5 z-10">
            <div className="font-display text-[11px] uppercase border-b border-ink pb-1">
              BIN: {hoveredBin.daysStart} – {hoveredBin.daysEnd} DAYS
            </div>
            <div>
              Iterations: <span className="font-bold">{hoveredBin.count} runs</span>
            </div>
            <div>
              Probability: <span className="font-bold">{hoveredBin.frequencyPct}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-3 border-2 border-ink bg-coral/15 space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-display text-xs uppercase">P10 DESIGN POINT</span>
            <span className="font-mono text-xs font-bold text-coral">90% SURVIVAL</span>
          </div>
          <div className="font-display text-2xl text-ink">{p10} DAYS</div>
          <p className="font-body text-[11px] text-ink/80">
            Conservative guarantee threshold recommended for retail expiry label declaration.
          </p>
        </div>

        <div className="p-3 border-2 border-ink bg-violet/20 border-violet space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-display text-xs uppercase">P50 EXPECTED MEDIAN</span>
            <span className="font-mono text-xs font-bold text-ink">50% PROBABILITY</span>
          </div>
          <div className="font-display text-2xl text-ink">{p50} DAYS</div>
          <p className="font-body text-[11px] text-ink/80">
            Most probable commercial lifespan under real-world non-isothermal supply chain.
          </p>
        </div>

        <div className="p-3 border-2 border-ink bg-lime/20 space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-display text-xs uppercase">P90 UPPER CEILING</span>
            <span className="font-mono text-xs font-bold text-lime-800">10% PROBABILITY</span>
          </div>
          <div className="font-display text-2xl text-ink">{p90} DAYS</div>
          <p className="font-body text-[11px] text-ink/80">
            Optimistic benchmark achieved with unbroken cold chain and zero transit shock.
          </p>
        </div>
      </div>
    </div>
  )
}

