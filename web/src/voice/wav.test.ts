import { describe, expect, it } from 'vitest'
import { encodeWav, mergeChunks, resample, TARGET_SAMPLE_RATE } from './wav'

function readStr(view: DataView, off: number, len: number) {
  let s = ''
  for (let i = 0; i < len; i++) s += String.fromCharCode(view.getUint8(off + i))
  return s
}

describe('wav encoder (Gnani Prisma upload format)', () => {
  it('writes a valid 16 kHz mono 16-bit PCM header', () => {
    const samples = new Float32Array(1600) // 0.1 s
    const view = new DataView(encodeWav(samples))
    expect(readStr(view, 0, 4)).toBe('RIFF')
    expect(readStr(view, 8, 4)).toBe('WAVE')
    expect(readStr(view, 12, 4)).toBe('fmt ')
    expect(view.getUint16(20, true)).toBe(1) // PCM
    expect(view.getUint16(22, true)).toBe(1) // mono
    expect(view.getUint32(24, true)).toBe(TARGET_SAMPLE_RATE)
    expect(view.getUint16(34, true)).toBe(16)
    expect(readStr(view, 36, 4)).toBe('data')
    expect(view.getUint32(40, true)).toBe(1600 * 2)
    expect(view.byteLength).toBe(44 + 1600 * 2)
  })

  it('clips and scales samples to int16', () => {
    const view = new DataView(encodeWav(new Float32Array([1, -1, 2, 0])))
    expect(view.getInt16(44, true)).toBe(32767)
    expect(view.getInt16(46, true)).toBe(-32768)
    expect(view.getInt16(48, true)).toBe(32767) // clipped
    expect(view.getInt16(50, true)).toBe(0)
  })

  it('resamples 48 kHz to 16 kHz', () => {
    const input = new Float32Array(48000).fill(0.5)
    const out = resample(input, 48000)
    expect(out.length).toBe(16000)
    expect(out[100]).toBeCloseTo(0.5)
  })

  it('merges recorder chunks in order', () => {
    const merged = mergeChunks([new Float32Array([1, 2]), new Float32Array([3])])
    expect(Array.from(merged)).toEqual([1, 2, 3])
  })
})
