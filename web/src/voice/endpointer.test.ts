import { describe, expect, it } from 'vitest'
import { createEndpointer, HANDS_FREE_DEFAULTS } from './recorder'

describe('hands-free end-of-speech detector', () => {
  const opts = { ...HANDS_FREE_DEFAULTS, silenceMs: 1000, noSpeechTimeoutMs: 5000, threshold: 0.1 }

  it('keeps listening while the user speaks and stops after a pause', () => {
    const ep = createEndpointer(opts)
    expect(ep(0, 0.02)).toBe('continue') // room noise
    expect(ep(500, 0.4)).toBe('continue') // speech starts
    expect(ep(1200, 0.3)).toBe('continue')
    expect(ep(1900, 0.02)).toBe('continue') // short breath (0.7 s)
    expect(ep(2300, 0.02)).toBe('stop') // 1.1 s of silence after speech
  })

  it('aborts (no upload) if nobody speaks', () => {
    const ep = createEndpointer(opts)
    expect(ep(0, 0.01)).toBe('continue')
    expect(ep(4000, 0.05)).toBe('continue')
    expect(ep(5100, 0.05)).toBe('abort')
  })

  it('does not stop on silence before any speech', () => {
    const ep = createEndpointer(opts)
    expect(ep(0, 0)).toBe('continue')
    expect(ep(2000, 0)).toBe('continue')
  })
})
