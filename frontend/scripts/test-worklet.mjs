// Runs src/audio/recorder-worklet.js in Node with a mocked AudioWorklet scope on a real speech WAV.
// Checks: every frame is exactly 1024 bytes; sample count matches 16 kHz; output matches a reference
// 16 kHz resample (SNR). Writes the 16 kHz output WAVs so they can be sent to Prisma REST.
// Usage: node scripts/test-worklet.mjs <speech.wav> [outDir]
import fs from 'node:fs'
import path from 'node:path'

const [, , inPath, outDir = '.'] = process.argv
if (!inPath) {
  console.error('usage: node scripts/test-worklet.mjs <speech.wav> [outDir]')
  process.exit(2)
}

function readWav(file) {
  const b = fs.readFileSync(file)
  let i = 12, rate = 0, ch = 1, data = null
  while (i + 8 <= b.length) {
    const id = b.toString('ascii', i, i + 4)
    let size = b.readUInt32LE(i + 4)
    if (id === 'fmt ') { ch = b.readUInt16LE(i + 10); rate = b.readUInt32LE(i + 12) }
    if (id === 'data') { if (size > b.length - i - 8) size = b.length - i - 8; data = b.subarray(i + 8, i + 8 + size); break }
    i += 8 + size + (size & 1)
  }
  const n = Math.floor(data.length / 2 / ch), f = new Float32Array(n)
  for (let k = 0; k < n; k++) { let s = 0; for (let c = 0; c < ch; c++) s += data.readInt16LE((k * ch + c) * 2); f[k] = s / ch / 32768 }
  return { rate, samples: f }
}

function resample(x, from, to) { // linear, for building test inputs and the reference
  const n = Math.floor((x.length * to) / from), y = new Float32Array(n), r = from / to
  for (let k = 0; k < n; k++) { const p = k * r, i = Math.floor(p), f = p - i; y[k] = (x[i] ?? 0) + ((x[i + 1] ?? x[i] ?? 0) - (x[i] ?? 0)) * f }
  return y
}

function writeWav(file, int16) {
  const h = Buffer.alloc(44)
  h.write('RIFF', 0); h.writeUInt32LE(36 + int16.length * 2, 4); h.write('WAVEfmt ', 8)
  h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(1, 22); h.writeUInt32LE(16000, 24)
  h.writeUInt32LE(32000, 28); h.writeUInt16LE(2, 32); h.writeUInt16LE(16, 34); h.write('data', 36)
  h.writeUInt32LE(int16.length * 2, 40)
  fs.writeFileSync(file, Buffer.concat([h, Buffer.from(int16.buffer, int16.byteOffset, int16.length * 2)]))
}

const src = fs.readFileSync(new URL('../src/audio/recorder-worklet.js', import.meta.url), 'utf8')
const speech = readWav(inPath)
let failed = false

for (const rate of [48000, 44100]) {
  let Proc
  const frames = []
  globalThis.sampleRate = rate
  globalThis.AudioWorkletProcessor = class { constructor() { this.port = { postMessage: (m) => { if (m instanceof ArrayBuffer) frames.push(m) } } } }
  globalThis.registerProcessor = (_n, c) => { Proc = c }
  new Function(src)()
  const p = new Proc()
  const input = resample(speech.samples, speech.rate, rate)
  for (let i = 0; i < input.length; i += 128) {
    const block = new Float32Array(128); block.set(input.subarray(i, i + 128))
    p.process([[block]])
  }
  const sizes = new Set(frames.map((f) => f.byteLength))
  const got = new Int16Array(frames.length * 512)
  frames.forEach((f, k) => got.set(new Int16Array(f), k * 512))
  const padded = Math.ceil(input.length / 128) * 128 // the last block is zero-padded to 128 samples
  const expected = Math.floor((padded * 16000) / rate)
  const produced = got.length + p.n
  // fidelity vs a reference resample of the original speech to 16 kHz (best alignment within ±3 samples)
  const ref = resample(speech.samples, speech.rate, 16000)
  let best = -Infinity
  for (let lag = -3; lag <= 3; lag++) {
    let sig = 0, err = 0
    for (let k = 100; k < Math.min(ref.length, got.length) - 100; k++) {
      const a = ref[k], b = got[k + lag] / 32768
      sig += a * a; err += (a - b) * (a - b)
    }
    best = Math.max(best, 10 * Math.log10(sig / err))
  }
  const ok = sizes.size === 1 && sizes.has(1024) && Math.abs(produced - expected) <= 2 && best > 10
  failed ||= !ok
  const out = path.join(outDir, `worklet_out_${rate}.wav`)
  writeWav(out, got)
  console.log(`${ok ? 'PASS' : 'FAIL'} ${rate} Hz: ${frames.length} frames, sizes=${[...sizes]}, samples=${produced} (expected ${expected}), SNR vs plain linear reference (no anti-alias filter)=${best.toFixed(1)} dB -> ${out}`)
}
process.exit(failed ? 1 : 0)
