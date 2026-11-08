import { useCallback, useEffect, useRef, useState } from 'react'
import { encodeWav, mergeChunks, resample, TARGET_SAMPLE_RATE } from './wav'

/** Prisma REST accepts clips up to 30 s; stop a little earlier to be safe. */
export const MAX_RECORD_SECONDS = 25

export type RecorderState = 'idle' | 'recording' | 'denied' | 'unsupported'

export function isRecordingSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    !!(window.AudioContext || (window as any).webkitAudioContext)
  )
}

export interface AutoStopOptions {
  /** Stop after this much silence once speech has started (end-of-utterance). */
  silenceMs: number
  /** Give up (no upload) if nobody speaks within this time. */
  noSpeechTimeoutMs: number
  /** Peak level (0..1) that counts as speech. */
  threshold: number
}

export const HANDS_FREE_DEFAULTS: AutoStopOptions = { silenceMs: 1200, noSpeechTimeoutMs: 8000, threshold: 0.08 }

/**
 * Pure end-of-speech detector, kept separate so it can be unit-tested.
 * Feed it (timeMs, level) samples; it answers 'continue' | 'stop' | 'abort'.
 */
export function createEndpointer(opts: AutoStopOptions) {
  let startedAt: number | null = null
  let lastVoice: number | null = null
  return (now: number, level: number): 'continue' | 'stop' | 'abort' => {
    if (startedAt === null) startedAt = now
    if (level >= opts.threshold) lastVoice = now
    if (lastVoice === null) return now - startedAt > opts.noSpeechTimeoutMs ? 'abort' : 'continue'
    return now - lastVoice > opts.silenceMs ? 'stop' : 'continue'
  }
}

/**
 * Tap-to-talk recorder that yields a 16 kHz mono WAV Blob.
 * Exposes a 0..1 input level for a live meter and auto-stops at MAX_RECORD_SECONDS,
 * or (hands-free) at end of speech when `start(HANDS_FREE_DEFAULTS)` is used.
 */
export function useWavRecorder(onComplete: (wav: Blob, seconds: number) => void) {
  const [state, setState] = useState<RecorderState>(isRecordingSupported() ? 'idle' : 'unsupported')
  const [level, setLevel] = useState(0)
  const [elapsed, setElapsed] = useState(0)

  const ctxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const nodeRef = useRef<ScriptProcessorNode | null>(null)
  const chunksRef = useRef<Float32Array[]>([])
  const startRef = useRef<number>(0)
  const timerRef = useRef<number | null>(null)
  const endpointRef = useRef<ReturnType<typeof createEndpointer> | null>(null)
  const levelRef = useRef(0)
  const onCompleteRef = useRef(onComplete)
  useEffect(() => {
    onCompleteRef.current = onComplete
  }, [onComplete])

  const cleanup = useCallback(() => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current)
    timerRef.current = null
    nodeRef.current?.disconnect()
    nodeRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    ctxRef.current?.close().catch(() => undefined)
    ctxRef.current = null
    setLevel(0)
  }, [])

  const stop = useCallback((discard = false) => {
    const ctx = ctxRef.current
    if (!ctx) return
    if (discard) {
      chunksRef.current = []
      cleanup()
      setState('idle')
      setElapsed(0)
      return
    }
    const rate = ctx.sampleRate
    const seconds = (performance.now() - startRef.current) / 1000
    const samples = resample(mergeChunks(chunksRef.current), rate, TARGET_SAMPLE_RATE)
    chunksRef.current = []
    cleanup()
    setState('idle')
    setElapsed(0)
    if (samples.length > TARGET_SAMPLE_RATE * 0.3) {
      onCompleteRef.current(new Blob([encodeWav(samples)], { type: 'audio/wav' }), seconds)
    }
  }, [cleanup])

  const start = useCallback(async (autoStop?: AutoStopOptions) => {
    if (!isRecordingSupported()) {
      setState('unsupported')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      const Ctx = window.AudioContext || (window as any).webkitAudioContext
      const ctx: AudioContext = new Ctx()
      const source = ctx.createMediaStreamSource(stream)
      // ScriptProcessorNode is deprecated but universally supported (incl. older Android WebViews).
      const node = ctx.createScriptProcessor(4096, 1, 1)
      chunksRef.current = []
      node.onaudioprocess = (e) => {
        const data = e.inputBuffer.getChannelData(0)
        chunksRef.current.push(new Float32Array(data))
        let peak = 0
        for (let i = 0; i < data.length; i += 64) peak = Math.max(peak, Math.abs(data[i]))
        levelRef.current = Math.min(1, peak * 1.6)
        setLevel(levelRef.current)
      }
      source.connect(node)
      node.connect(ctx.destination)
      ctxRef.current = ctx
      streamRef.current = stream
      nodeRef.current = node
      startRef.current = performance.now()
      endpointRef.current = autoStop ? createEndpointer(autoStop) : null
      setElapsed(0)
      setState('recording')
      timerRef.current = window.setInterval(() => {
        const secs = (performance.now() - startRef.current) / 1000
        setElapsed(secs)
        if (secs >= MAX_RECORD_SECONDS) {
          stop()
          return
        }
        const ep = endpointRef.current
        if (ep) {
          const verdict = ep(performance.now(), levelRef.current)
          if (verdict === 'stop') stop()
          else if (verdict === 'abort') stop(true)
        }
      }, 100)
    } catch {
      cleanup()
      setState('denied')
    }
  }, [cleanup, stop])

  useEffect(() => cleanup, [cleanup])

  return { state, level, elapsed, start, stop }
}
