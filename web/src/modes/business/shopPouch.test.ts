import { describe, expect, it } from 'vitest'
import { pouchKind, scaledPackCost, sellerSpec } from './shopPouch'

describe('shop pouch wording', () => {
  it('classifies film stacks into words a shopkeeper knows', () => {
    expect(pouchKind(['PET', 'AluFoil', 'LLDPE'])).toBe('foil')
    expect(pouchKind(['BOPP', 'VMBOPP', 'CPP'])).toBe('metal')
    expect(pouchKind(['PET', 'VMPET', 'LLDPE'])).toBe('metal')
    expect(pouchKind(['Perf-BOPP', 'LDPE'])).toBe('breathable')
    expect(pouchKind(['PET', 'LLDPE'])).toBe('clear_strong')
    expect(pouchKind(['BOPP', 'CPP'])).toBe('clear')
  })

  it('turns gauge shorthand into what to say to the seller', () => {
    expect(sellerSpec('20u BOPP / 18u VMBOPP / 40u CPP', [])).toBe('20 micron BOPP / 18 micron VMBOPP / 40 micron CPP')
    expect(sellerSpec(null, ['PET', 'LLDPE'])).toBe('PET / LLDPE')
  })

  it('scales pouch cost with film area (weight^2/3)', () => {
    expect(scaledPackCost(1.75, 200)).toBe(1.75)
    expect(scaledPackCost(1.75, 1000)).toBeCloseTo(5.12, 1)
    expect(scaledPackCost(1.75, 100)).toBeCloseTo(1.1, 1)
  })
})
