import React, { useState } from 'react'
import type { PackagingSpecSheet, BusinessInputState, RfqSpecification } from '../types'
import { generateRfqData } from '../engine'
import { getApiUrl } from '../../../api/config'

interface RfqGeneratorProps {
  input: BusinessInputState
  structure: PackagingSpecSheet
  onClose?: () => void
}

export const RfqGenerator: React.FC<RfqGeneratorProps> = ({ input, structure, onClose }) => {
  const [brandName, setBrandName] = useState('Organic Farm Spices India Pvt Ltd')
  const [converterName, setConverterName] = useState('Apex Flexible Films & Laminates Ltd')
  const [orderQuantity, setOrderQuantity] = useState(input.annualPackVolume)
  const [copied, setCopied] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const rfq: RfqSpecification = generateRfqData(
    { ...input, annualPackVolume: orderQuantity },
    structure,
    brandName,
    converterName
  )

  const formattedRfqText = `
================================================================================
AAVARAN AI CONVERTER REQUEST FOR QUOTATION (RFQ)
RFQ REF: ${rfq.rfqId} | DATE: ${rfq.createdAt}
================================================================================

1. PARTIES & COMMERCIAL TARGETS
--------------------------------------------------------------------------------
Brand / Buyer:          ${rfq.brandName}
Target Converter:       ${rfq.converterName}
Order Target Volume:    ${rfq.targetOrderQuantity.toLocaleString()} units (${rfq.orderType.replace('_', ' ').toUpperCase()})
Delivery Jurisdiction:  ${input.destinationMarket === 'IN' ? 'Domestic India (FSSAI / PWM 2022)' : 'Export Global'}

2. SPECIFIED PACKAGING STRUCTURE
--------------------------------------------------------------------------------
Structure Description:  ${structure.name}
Layer Sequence:         ${structure.layerStackDisplay}
Composite Gauge:        ${structure.compositeThicknessUm} µm (Tolerance: ±5% max across reel)
EPR Category:           ${structure.eprCategory} (${structure.recyclabilityStatus})
Target COF:             Static: ${structure.cofStatic} | Dynamic: ${structure.cofDynamic} (ASTM D1894)

3. NOMINAL GAUGE & LAYER TOLERANCES
--------------------------------------------------------------------------------
${rfq.nominalGaugesWithTolerances
  .map(
    (g, i) =>
      `  [Layer ${i + 1}] ${g.layer.padEnd(42, ' ')} : ${g.nominalUm} µm (Tol: ±${g.tolerancePct}%)`
  )
  .join('\n')}

4. ASTM LABORATORY TEST METHODS & CONVERTER ACCEPTANCE CRITERIA
--------------------------------------------------------------------------------
${rfq.testMethodsAndAcceptance
  .map(
    (t) =>
      `  * ${t.property.padEnd(38, ' ')} [${t.standard}] : ${t.acceptanceCriteria}`
  )
  .join('\n')}

5. DIMENSIONS & FINISHING
--------------------------------------------------------------------------------
${
  rfq.orderType === 'premade_pouches' && rfq.pouchDimensionsMm
    ? `  Pouch Style: Center Seal / Stand-up Pouch with Tear Notch & Round Corners\n  Dimensions: ${rfq.pouchDimensionsMm.width} mm (W) x ${rfq.pouchDimensionsMm.height} mm (H) + ${rfq.pouchDimensionsMm.bottomGusset} mm (Gusset)`
    : rfq.rollDimensionsMm
    ? `  Roll Width: ${rfq.rollDimensionsMm.width} mm | Repeat Length: ${rfq.rollDimensionsMm.repeatLength} mm\n  Core ID: ${rfq.rollDimensionsMm.coreDiameter} mm (3") | Max Roll OD: ${rfq.rollDimensionsMm.maxRollOd} mm | Winding: Face-Out Left Edge Eyemark`
    : ''
}

6. DEFECT ACCEPTANCE QUALITY LIMITS (AQL)
--------------------------------------------------------------------------------
  - Critical Defects (Pinholes, delamination, channel leakers): AQL ${rfq.defectTolerancesAql.critical} (Zero Tolerance)
  - Major Defects (Seal strength < 20 N/15mm, optical scuffing): AQL ${rfq.defectTolerancesAql.major}
  - Minor Defects (Core telescoping < 1mm, edge trimming): AQL ${rfq.defectTolerancesAql.minor}

7. MANDATORY CONVERTER COMPLIANCE & TERMS
--------------------------------------------------------------------------------
${rfq.commercialTerms.map((term, i) => `  ${i + 1}. ${term}`).join('\n')}

================================================================================
Generated via Aavaran AI | Strict FSSAI & PWM Standard
================================================================================
`.trim()

  const handleCopyText = async () => {
    try {
      await navigator.clipboard.writeText(formattedRfqText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch {
      // Fallback
    }
  }

  const handleDownloadPdf = async () => {
    setDownloading(true)
    setDownloadError(null)
    try {
      const commodityName = input.commodityName || 'Produce'
      const rfqPayload = {
        commodity: commodityName,
        structure_rank: structure.rank || 1,
        brand_name: brandName,
        converter_name: converterName,
        order_quantity: orderQuantity,
        structure_name: structure.name,
        structure: structure,
        rfq_data: rfq,
      }

      const response = await fetch(getApiUrl('/api/v1/rfq/pdf'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rfqPayload),
      })

      if (!response.ok) {
        let errorDetail = 'PDF generation failed'
        try {
          const err = await response.json()
          errorDetail = err.detail || errorDetail
        } catch {
          // Response body was not JSON
        }
        throw new Error(errorDetail)
      }

      // CRITICAL: get ArrayBuffer, not .text() or .json()
      const arrayBuffer = await response.arrayBuffer()
      const blob = new Blob([arrayBuffer], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)

      const link = document.createElement('a')
      link.href = url
      link.download = `Aavaran_RFQ_${commodityName.replace(/\s+/g, '_')}_${structure.rank || 1}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      // Clean up the object URL after a short delay
      setTimeout(() => URL.revokeObjectURL(url), 5000)
    } catch (err: any) {
      setDownloadError(err.message || 'PDF generation failed')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="border-3 border-ink bg-paper shadow-[8px_8px_0_var(--ink)] p-5 sm:p-7 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b-3 border-ink pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-display text-xs uppercase bg-cyan text-ink px-2 py-0.5 border border-ink">
              FIRST-CLASS PROCUREMENT FEATURE
            </span>
            <span className="font-mono text-xs font-bold text-ink/70">{rfq.rfqId}</span>
          </div>
          <h2 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0">
            Converter RFQ Generator
          </h2>
          <p className="font-body text-xs sm:text-sm text-ink/80 mt-1">
            Ready-to-send commercial specification sheet with ASTM test methods, layer tolerances, and acceptance thresholds.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="font-display text-xs uppercase px-3 py-2 border-2 border-ink bg-paper hover:bg-grey/40 cursor-pointer shadow-[2px_2px_0_var(--ink)]"
            >
              ✕ CLOSE
            </button>
          )}
        </div>
      </div>

      {/* Customization Inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 border-2 border-ink bg-grey/20">
        <div>
          <label className="block font-mono text-xs font-bold uppercase mb-1">
            Your Brand / Company Name
          </label>
          <input
            type="text"
            value={brandName}
            onChange={(e) => setBrandName(e.target.value)}
            className="w-full border-2 border-ink p-2 font-mono text-xs bg-paper text-ink"
          />
        </div>

        <div>
          <label className="block font-mono text-xs font-bold uppercase mb-1">
            Target Converter / Supplier
          </label>
          <input
            type="text"
            value={converterName}
            onChange={(e) => setConverterName(e.target.value)}
            className="w-full border-2 border-ink p-2 font-mono text-xs bg-paper text-ink"
          />
        </div>

        <div>
          <label className="block font-mono text-xs font-bold uppercase mb-1">
            Order Quantity
          </label>
          <input
            type="number"
            min="5000"
            max="10000000"
            step="10000"
            value={orderQuantity}
            onChange={(e) => setOrderQuantity(Number(e.target.value))}
            className="w-full border-2 border-ink p-2 font-mono text-xs bg-paper text-ink"
          />
        </div>
      </div>

      {/* Structure Preview Banner */}
      <div className="p-3 border-2 border-ink bg-cyan/20 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <span className="font-mono text-[10px] uppercase font-bold text-ink/70">
            SPECIFICATION FOR RFQ
          </span>
          <div className="font-display text-base text-ink">{structure.name}</div>
          <div className="font-mono text-xs text-ink/80">{structure.layerStackDisplay}</div>
        </div>
        <div className="flex gap-2">
          <span className="font-mono text-xs font-bold bg-paper px-2 py-1 border border-ink">
            GAUGE: {structure.compositeThicknessUm} µm (±5%)
          </span>
          <span className="font-mono text-xs font-bold bg-yellow px-2 py-1 border border-ink">
            {structure.eprCategory}
          </span>
        </div>
      </div>

      {/* Main RFQ Text Box (Scrollable copyable preview) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-display text-xs uppercase text-ink">
            Complete Structured Converter Brief (Plain Text)
          </span>
          <span className="font-mono text-[10px] text-ink/70">
            Copy into Email or WhatsApp Converter Chat
          </span>
        </div>
        <textarea
          readOnly
          value={formattedRfqText}
          rows={12}
          className="w-full border-3 border-ink p-3 font-mono text-xs bg-paper text-ink leading-relaxed select-all"
        />
      </div>

      {/* Error Banner */}
      {downloadError && (
        <div className="w-full p-3 bg-red-100 border-3 border-ink text-ink font-mono text-xs flex items-center justify-between gap-3 shadow-[3px_3px_0_var(--ink)]">
          <div className="flex items-center gap-2">
            <span className="text-base text-red-600 font-bold">⚠️</span>
            <span>
              <strong className="text-red-700">PDF Generation Error:</strong> {downloadError}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setDownloadError(null)}
            className="text-ink font-bold px-2 py-0.5 border-2 border-ink bg-paper hover:bg-grey/40 cursor-pointer text-xs"
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
        <div className="font-mono text-xs text-ink/80">
          Generated with ASTM D3985, F1249, F88, D882, and F392 Gelbo acceptance limits.
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          <button
            type="button"
            onClick={handleCopyText}
            className={`flex-1 sm:flex-initial font-display text-xs sm:text-sm uppercase px-5 py-3 border-3 border-ink shadow-[3px_3px_0_var(--ink)] cursor-pointer transition-all ${
              copied
                ? 'bg-lime text-ink'
                : 'bg-yellow text-ink hover:bg-yellow/80 hover:translate-y-[-1px]'
            }`}
          >
            {copied ? '✓ COPIED TO CLIPBOARD!' : '📋 COPY FORMATTED RFQ'}
          </button>

          <button
            type="button"
            disabled={downloading}
            onClick={handleDownloadPdf}
            className={`flex-1 sm:flex-initial font-display text-xs sm:text-sm uppercase px-6 py-3 bg-cyan text-ink border-3 border-ink shadow-[4px_4px_0_var(--ink)] transition-all flex items-center justify-center gap-2 ${
              downloading
                ? 'opacity-70 cursor-wait'
                : 'hover:bg-cyan/80 hover:translate-y-[-2px] hover:shadow-[6px_6px_0_var(--ink)] active:translate-y-[1px] active:shadow-[2px_2px_0_var(--ink)] cursor-pointer'
            }`}
          >
            {downloading ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-1 h-4 w-4 text-ink"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                  />
                </svg>
                <span>GENERATING PDF…</span>
              </>
            ) : (
              <>
                <span>📥</span>
                <span>DOWNLOAD OFFICIAL PDF RFQ</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
