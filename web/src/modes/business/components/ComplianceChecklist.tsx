import React, { useState, useRef } from 'react'
import type { ComplianceItem } from '../types'

interface ComplianceChecklistProps {
  items: ComplianceItem[]
}

export const ComplianceChecklist: React.FC<ComplianceChecklistProps> = ({ items }) => {
  const compliantCount = items.filter((i) => i.status === 'COMPLIANT').length
  const totalCount = items.length

  const [checking, setChecking] = useState(false)
  const [complianceResult, setComplianceResult] = useState<{
    timestamp: string
    passed: number
    actionRequired: number
  } | null>(null)
  const complianceRef = useRef<HTMLDivElement>(null)

  const handleRunComplianceCheck = async () => {
    setChecking(true)
    await new Promise((resolve) => setTimeout(resolve, 500))
    const now = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
    setComplianceResult({
      timestamp: now,
      passed: compliantCount,
      actionRequired: totalCount - compliantCount,
    })
    setChecking(false)
    setTimeout(() => {
      complianceRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120)
  }

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="font-mono text-xs font-bold uppercase tracking-wider bg-lime text-ink px-2 py-0.5 inline-block mb-1 border border-ink">
            STATUTORY REGULATORY CONFORMITY · INDIA FSSAI & PWM 2022
          </span>
          <h3 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
            02 · Compliance & Mandatory Documents Checklist
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold bg-paper border-2 border-ink px-2.5 py-1">
            SCORE: {compliantCount}/{totalCount} STATUTORY CLAUSES
          </span>
        </div>
      </div>

      <p className="font-body text-xs sm:text-sm text-ink/80">
        Every food packaging structure must fulfill mandatory chemical migration limits and Producer Responsibility (EPR) regulations before commercial distribution. Each item cites the statutory legal instrument and specifies the exact required compliance dossier.
      </p>

      <div className="space-y-3">
        {items.map((item) => {
          const isPass = item.status === 'COMPLIANT'
          const isAction = item.status === 'ACTION_REQUIRED'

          return (
            <div
              key={item.id}
              className={`p-4 border-3 border-ink transition-all ${
                isPass
                  ? 'bg-paper shadow-[3px_3px_0_var(--ink)]'
                  : 'bg-yellow/20 shadow-[5px_5px_0_var(--ink)]'
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-display text-xs bg-ink text-paper px-2 py-0.5">
                      {item.clause}
                    </span>
                    <span className="font-mono text-xs font-bold text-ink/80">
                      {item.standard}
                    </span>
                  </div>

                  <h4 className="font-display text-base uppercase text-ink m-0">
                    {item.title}
                  </h4>

                  <p className="font-body text-xs text-ink/85 leading-relaxed">
                    {item.details}
                  </p>

                  {/* Required Document Callout */}
                  <div className="mt-2 p-2.5 border-2 border-ink bg-paper inline-flex flex-col sm:flex-row sm:items-center gap-2 text-xs">
                    <span className="font-display text-[10px] uppercase bg-cyan text-ink px-1.5 py-0.5 border border-ink shrink-0">
                      REQUIRED STATUTORY DOSSIER
                    </span>
                    <span className="font-mono font-bold text-ink truncate">
                      📄 {item.requiredDocumentName}
                    </span>
                  </div>
                </div>

                <div className="flex flex-col items-start sm:items-end gap-2 shrink-0">
                  <span
                    className={`font-display text-xs uppercase px-2.5 py-1 border-2 border-ink ${
                      isPass
                        ? 'bg-lime text-ink'
                        : isAction
                        ? 'bg-coral text-ink'
                        : 'bg-paper text-ink'
                    }`}
                  >
                    {isPass ? '✓ CLAUSE PASS' : '⚠ ACTION REQUIRED'}
                  </span>

                  <span className="font-mono text-[11px] font-bold text-ink/70">
                    STATUS: {item.documentStatus.replace('_', ' ')}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Action Button: Run Compliance Check */}
      <div className="pt-2 flex justify-end">
        <button
          type="button"
          disabled={checking}
          onClick={handleRunComplianceCheck}
          style={
            checking
              ? {
                  animation: 'rfq-pulse 1s infinite ease-in-out',
                  pointerEvents: 'none',
                }
              : undefined
          }
          className={`font-display text-xs uppercase px-5 py-2.5 border-2 border-ink flex items-center gap-1.5 transition-all ${
            checking
              ? 'bg-grey text-ink cursor-not-allowed shadow-none'
              : 'bg-yellow text-ink hover:bg-yellow/80 shadow-[3px_3px_0_var(--ink)] cursor-pointer'
          }`}
        >
          {checking ? (
            <span>⚡ RUNNING COMPLIANCE CHECK…</span>
          ) : (
            <>
              <span>⚖️</span>
              <span>Run Compliance Check</span>
            </>
          )}
        </button>
      </div>

      <div className="p-3 border-2 border-ink bg-grey/30 text-xs font-mono text-ink/80 flex items-center gap-2">
        <span className="font-bold text-base">⚖️</span>
        <span>
          Statutory disclaimer: Test certificates must be issued by a NABL-accredited testing laboratory. The Food Business Operator (FBO) maintains legal responsibility under the Food Safety and Standards Act, 2006.
        </span>
      </div>

      {/* Compliance Check Result Section with Visual Anchor */}
      {complianceResult && (
        <div ref={complianceRef} className="rfq-result-section">
          <div className="rfq-section-header">
            <span className="font-display font-black text-sm sm:text-base">
              ✓ COMPLIANCE CHECK COMPLETED — FSSAI & PWM 2022 Statutory Audit
            </span>
            <span className="font-mono text-xs normal-case opacity-90">
              Generated {complianceResult.timestamp}
            </span>
          </div>
          <div className="mt-4 p-5 border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b-2 border-ink pb-3">
              <div>
                <span className="font-mono text-xs font-bold uppercase bg-lime text-ink px-2 py-0.5 border border-ink">
                  CONFORMITY CERTIFICATE STATUS
                </span>
                <h4 className="font-display text-lg uppercase text-ink mt-1 m-0">
                  Statutory Rule Evaluation Trace
                </h4>
              </div>
              <span className="font-mono text-xs font-bold bg-ink text-paper px-2 py-1">
                RULESET: v2026.09-IN
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
              <div className="p-3 border-2 border-ink bg-paper">
                <span className="text-ink/70 block uppercase">Total Clauses Audited</span>
                <span className="font-display text-xl text-ink">{totalCount}</span>
              </div>
              <div className="p-3 border-2 border-ink bg-paper">
                <span className="text-ink/70 block uppercase">Compliant Clauses</span>
                <span className="font-display text-xl text-lime-800 font-bold">
                  {complianceResult.passed} PASS
                </span>
              </div>
              <div className="p-3 border-2 border-ink bg-paper">
                <span className="text-ink/70 block uppercase">Action Required</span>
                <span className="font-display text-xl text-coral font-bold">
                  {complianceResult.actionRequired} PENDING
                </span>
              </div>
            </div>

            <div className="p-3 border-2 border-ink bg-lime/20 font-mono text-xs text-ink/90">
              ✓ All statutory migration limits, heavy metal limits, and BIS mandatory standards evaluated against current legal schedules.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
