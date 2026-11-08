import React from 'react'
import type { EvaluatedRule, ComplianceSummary } from '../types'

interface ComplianceRuleTraceProps {
  rules?: EvaluatedRule[]
  compliance?: ComplianceSummary | null
  traceItems?: EvaluatedRule[]
}

export const ComplianceRuleTrace: React.FC<ComplianceRuleTraceProps> = ({
  rules,
  compliance,
  traceItems,
}) => {
  const ruleList = rules || compliance?.rules_evaluated || traceItems || []

  const passCount = ruleList.filter((r) => r.status === 'PASS').length
  const warnCount = ruleList.filter((r) => r.status === 'WARN').length
  const blockCount = ruleList.filter((r) => r.status === 'BLOCK').length

  const getStatusBadge = (status: 'PASS' | 'WARN' | 'BLOCK') => {
    switch (status) {
      case 'PASS':
        return (
          <span className="font-mono text-xs font-bold px-2 py-0.5 border border-ink bg-lime text-ink">
            PASS
          </span>
        )
      case 'WARN':
        return (
          <span className="font-mono text-xs font-bold px-2 py-0.5 border border-ink bg-yellow text-ink">
            WARN
          </span>
        )
      case 'BLOCK':
        return (
          <span className="font-mono text-xs font-bold px-2 py-0.5 border border-ink bg-coral text-white">
            BLOCK
          </span>
        )
      default:
        return (
          <span className="font-mono text-xs font-bold px-2 py-0.5 border border-ink bg-grey text-ink">
            {status}
          </span>
        )
    }
  }

  return (
    <div className="border-3 border-ink bg-paper shadow-[6px_6px_0_var(--ink)] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-3 border-ink pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider bg-violet text-ink px-2 py-0.5 border border-ink">
              STATUTORY COMPLIANCE TRACE
            </span>
            {compliance?.destination_market && (
              <span className="font-mono text-xs font-bold uppercase bg-white text-ink px-2 py-0.5 border border-ink">
                MARKET: {compliance.destination_market}
              </span>
            )}
            <span className="font-mono text-xs font-bold text-ink/70">
              MANDATORY STATUTORY AUDIT
            </span>
          </div>
          <h3 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            07 · Compliance Rule Trace Log
          </h3>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Automated statutory evaluations across FSSAI 2018, PWM 2022 EPR rules, and Legal Metrology packaging clauses.
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="px-2 py-1 bg-lime text-ink border border-ink font-bold">
            PASS: {passCount}
          </span>
          <span className="px-2 py-1 bg-yellow text-ink border border-ink font-bold">
            WARN: {warnCount}
          </span>
          <span className="px-2 py-1 bg-coral text-white border border-ink font-bold">
            BLOCK: {blockCount}
          </span>
        </div>
      </div>

      {ruleList.length === 0 ? (
        <div className="py-10 text-center font-mono text-sm text-ink/60 border-2 border-dashed border-ink/30">
          Run a recommendation to inspect statutory compliance trace.
        </div>
      ) : (
        <div className="overflow-x-auto border-3 border-ink bg-white">
          <table className="w-full border-collapse font-mono text-xs text-left">
            <thead>
              <tr className="bg-ink text-paper border-b-2 border-ink">
                <th className="py-2.5 px-3 uppercase tracking-wider font-bold w-40">Rule ID</th>
                <th className="py-2.5 px-3 uppercase tracking-wider font-bold w-48">Instrument</th>
                <th className="py-2.5 px-3 uppercase tracking-wider font-bold w-32">Clause</th>
                <th className="py-2.5 px-3 uppercase tracking-wider font-bold w-24">Status</th>
                <th className="py-2.5 px-3 uppercase tracking-wider font-bold">Effect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink/20">
              {ruleList.map((rule, idx) => (
                <tr
                  key={rule.rule_id || idx}
                  className={`hover:bg-cream/50 transition-colors ${
                    rule.status === 'BLOCK' ? 'bg-coral/10' : rule.status === 'WARN' ? 'bg-yellow/10' : ''
                  }`}
                >
                  <td className="py-2.5 px-3 font-bold text-ink whitespace-nowrap">
                    {rule.rule_id}
                  </td>
                  <td className="py-2.5 px-3 text-ink/80">
                    {rule.instrument}
                  </td>
                  <td className="py-2.5 px-3 text-ink/70">
                    {rule.clause}
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    {getStatusBadge(rule.status)}
                  </td>
                  <td className="py-2.5 px-3 font-body text-xs text-ink/90">
                    {rule.effect}
                    {rule.message && rule.message !== rule.effect && (
                      <span className="block text-[11px] text-ink/60 mt-0.5">{rule.message}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

