import workletUrl from '../audio/recorder-worklet.js?url'

export interface Mic {
  stop: () => Promise<void>
  /** The real AudioContext rate the browser chose (often 48000 or 44100). */
  sampleRate: number
}

export interface MicOptions {
  echoCancellation?: boolean
  noiseSuppression?: boolean
  autoGainControl?: boolean
  /** RMS of the raw mic signal (0..1), about 10 times a second. */
  onLevel?: (rms: number) => void
}

/** Start the microphone; onFrame receives 1024-byte PCM16 mono 16 kHz chunks. */
export async function startMic(onFrame: (frame: ArrayBuffer) => void, opts: MicOptions = {}): Promise<Mic> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new MicError('unsupported')
  }
  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: opts.echoCancellation ?? true,
        noiseSuppression: opts.noiseSuppression ?? true,
        autoGainControl: opts.autoGainControl ?? true,
      },
    })
  } catch (e) {
    const name = (e as DOMException)?.name
    throw new MicError(name === 'NotAllowedError' || name === 'SecurityError' ? 'denied' : name === 'NotFoundError' ? 'none' : 'failed')
  }
  const ctx = new AudioContext()
  await ctx.audioWorklet.addModule(workletUrl)
  const src = ctx.createMediaStreamSource(stream)
  const node = new AudioWorkletNode(ctx, 'pcm16k')
  node.port.onmessage = (e: MessageEvent<ArrayBuffer | { type: string; rms: number }>) => {
    if (e.data instanceof ArrayBuffer) onFrame(e.data)
    else if (e.data?.type === 'level') opts.onLevel?.(e.data.rms)
  }
  const mute = ctx.createGain()
  mute.gain.value = 0 // keep the graph running without echoing the mic to the speaker
  src.connect(node)
  node.connect(mute)
  mute.connect(ctx.destination)
  if (ctx.state === 'suspended') await ctx.resume()
  console.info(`[mic] AudioContext.sampleRate=${ctx.sampleRate} Hz -> 16000 Hz, 1024-byte frames`)
  return {
    sampleRate: ctx.sampleRate,
    stop: async () => {
      node.port.onmessage = null
      stream.getTracks().forEach((t) => t.stop())
      src.disconnect()
      node.disconnect()
      await ctx.close()
    },
  }
}

export type MicProblem = 'denied' | 'none' | 'unsupported' | 'failed'

export class MicError extends Error {
  problem: MicProblem
  constructor(problem: MicProblem) {
    super(problem)
    this.problem = problem
  }
}

/** PCM16 mono 16 kHz chunks -> a WAV Blob (kept in memory only). */
export function pcmToWav(chunks: ArrayBuffer[]): Blob {
  const dataLen = chunks.reduce((n, c) => n + c.byteLength, 0)
  const header = new ArrayBuffer(44)
  const v = new DataView(header)
  const str = (o: number, s: string) => [...s].forEach((ch, i) => v.setUint8(o + i, ch.charCodeAt(0)))
  str(0, 'RIFF')
  v.setUint32(4, 36 + dataLen, true)
  str(8, 'WAVE')
  str(12, 'fmt ')
  v.setUint32(16, 16, true)
  v.setUint16(20, 1, true) // PCM
  v.setUint16(22, 1, true) // mono
  v.setUint32(24, 16000, true)
  v.setUint32(28, 32000, true)
  v.setUint16(32, 2, true)
  v.setUint16(34, 16, true)
  str(36, 'data')
  v.setUint32(40, dataLen, true)
  return new Blob([header, ...chunks], { type: 'audio/wav' })
}
