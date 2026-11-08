import { describe, expect, it } from 'vitest'

/**
 * Convert standard sRGB 0-255 channel to linear relative luminance component
 * according to WCAG 2.1 specifications.
 */
function sRGBToLinear(c: number): number {
  const norm = c / 255
  return norm <= 0.04045 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4)
}

/**
 * Calculate WCAG 2.1 relative luminance for a given hex color code.
 */
export function getRelativeLuminance(hex: string): number {
  const sanitized = hex.replace('#', '')
  const r = parseInt(sanitized.slice(0, 2), 16)
  const g = parseInt(sanitized.slice(2, 4), 16)
  const b = parseInt(sanitized.slice(4, 6), 16)

  return (
    0.2126 * sRGBToLinear(r) +
    0.7152 * sRGBToLinear(g) +
    0.0722 * sRGBToLinear(b)
  )
}

/**
 * Calculate WCAG 2.1 contrast ratio between two hex colors.
 */
export function getContrastRatio(hex1: string, hex2: string): number {
  const l1 = getRelativeLuminance(hex1)
  const l2 = getRelativeLuminance(hex2)
  const lighter = Math.max(l1, l2)
  const darker = Math.min(l1, l2)
  return (lighter + 0.05) / (darker + 0.05)
}

export const TOKENS = {
  paper: '#FFFDF2',
  ink: '#0B0B0B',
  yellow: '#FFE500',
  cyan: '#5CE1FF',
  lime: '#C9FF3D',
  coral: '#FF6B52',
  violet: '#C3A6FF',
  grey: '#E8E4D6',
  darkPaper: '#121212',
  darkInk: '#FFFDF2',
}

describe('Neo-Brutalist Design System Contrast Ratio (WCAG AAA >= 7:1)', () => {
  const bodyTextTokenPairs: Array<{ name: string; fg: string; bg: string }> = [
    { name: 'Ink body text on Paper ground', fg: TOKENS.ink, bg: TOKENS.paper },
    { name: 'Ink body text on Yellow (Primary button / Kisan tab)', fg: TOKENS.ink, bg: TOKENS.yellow },
    { name: 'Ink body text on Cyan (Info / Business tab)', fg: TOKENS.ink, bg: TOKENS.cyan },
    { name: 'Ink body text on Lime (Success / Safe badge)', fg: TOKENS.ink, bg: TOKENS.lime },
    { name: 'Ink body text on Coral (Safety block)', fg: TOKENS.ink, bg: TOKENS.coral },
    { name: 'Ink body text on Violet (Expert tab)', fg: TOKENS.ink, bg: TOKENS.violet },
    { name: 'Ink body text on Grey (Table alternate stripes / disabled)', fg: TOKENS.ink, bg: TOKENS.grey },
    { name: 'Paper text on Ink header (SpecTable header)', fg: TOKENS.paper, bg: TOKENS.ink },
    { name: 'Dark Ink on Dark Paper ground (Dark Mode)', fg: TOKENS.darkInk, bg: TOKENS.darkPaper },
  ]

  bodyTextTokenPairs.forEach(({ name, fg, bg }) => {
    it(`should guarantee contrast ratio >= 7:1 for ${name}`, () => {
      const ratio = getContrastRatio(fg, bg)
      expect(ratio).toBeGreaterThanOrEqual(7.0)
    })
  })
})
