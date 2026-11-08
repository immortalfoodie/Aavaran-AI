import React from 'react'
import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import fs from 'fs'
import path from 'path'
import { StructureCards } from '../../src/modes/business/components/StructureCards'
import { ShelfLifeBandChart } from '../../src/modes/business/components/ShelfLifeBandChart'
import { ComplianceChecklist } from '../../src/modes/business/components/ComplianceChecklist'
import { ParetoFrontierPlot } from '../../src/modes/expert/components/ParetoFrontierPlot'
import { calculateBusinessResults, DEFAULT_BUSINESS_INPUT } from '../../src/modes/business/engine'
import { generateParetoCandidates } from '../../src/modes/expert/engine'

describe('RFQ & Async Generation Visual Feedback (Parts A, B, C, D)', () => {
  const businessResults = calculateBusinessResults(DEFAULT_BUSINESS_INPUT)
  const sampleStructure = businessResults.structures[0]

  it('Part A: verifies rfq-pulse keyframe and utility classes in tokens.css and index.css', () => {
    const tokensCss = fs.readFileSync(path.resolve(__dirname, '../../src/design/tokens.css'), 'utf-8')
    const indexCss = fs.readFileSync(path.resolve(__dirname, '../../src/index.css'), 'utf-8')

    expect(tokensCss).toContain('@keyframes rfq-pulse')
    expect(tokensCss).toContain('opacity: 0.4')
    expect(tokensCss).toContain('.rfq-pulse-loading')
    expect(tokensCss).toContain('.rfq-result-section')
    expect(tokensCss).toContain('border-top: 6px solid var(--yellow)')
    expect(tokensCss).toContain('.rfq-section-header')

    expect(indexCss).toContain('@keyframes rfq-pulse')
    expect(indexCss).toContain('.rfq-result-section')
    expect(indexCss).toContain('.rfq-section-header')
  })

  it('Part A: StructureCards displays idle button state normally', () => {
    const html = renderToString(
      <StructureCards
        structures={businessResults.structures}
        selectedStructureId={sampleStructure.structureId}
        onSelectStructure={() => {}}
        onOpenRfq={() => {}}
        rfqLoading={false}
        loadingStructureId={null}
      />
    )

    expect(html).toContain('GENERATE CONVERTER RFQ SPEC')
    expect(html).not.toContain('⚡ GENERATING RFQ…')
  })

  it('Part A: StructureCards renders loading state with pulsing animation, grey background, and disabled state', () => {
    const html = renderToString(
      <StructureCards
        structures={businessResults.structures}
        selectedStructureId={sampleStructure.structureId}
        onSelectStructure={() => {}}
        onOpenRfq={() => {}}
        rfqLoading={true}
        loadingStructureId={sampleStructure.structureId}
      />
    )

    expect(html).toContain('⚡ GENERATING RFQ…')
    expect(html).toContain('rfq-pulse 1s infinite ease-in-out')
    expect(html).toContain('bg-grey')
    expect(html).toContain('disabled')
    expect(html).toContain('pointer-events:none')
  })

  it('Part D: ShelfLifeBandChart includes Generate Shelf Life Report button', () => {
    const html = renderToString(
      <ShelfLifeBandChart
        structure={sampleStructure}
        targetDays={DEFAULT_BUSINESS_INPUT.targetShelfLifeDays}
        routeLegs={DEFAULT_BUSINESS_INPUT.routeLegs}
      />
    )

    expect(html).toContain('Generate Shelf Life Report')
  })

  it('Part D: ComplianceChecklist includes Run Compliance Check button', () => {
    const html = renderToString(
      <ComplianceChecklist items={businessResults.complianceItems} />
    )

    expect(html).toContain('Run Compliance Check')
  })

  it('Part D: ParetoFrontierPlot includes Compute Pareto Frontier button', () => {
    const candidates = generateParetoCandidates()
    const html = renderToString(
      <ParetoFrontierPlot candidates={candidates} />
    )

    expect(html).toContain('Compute Pareto Frontier')
  })
})
