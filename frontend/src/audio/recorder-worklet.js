// AudioWorklet: mic audio at the context rate (usually 48000 or 44100 Hz) -> 16 kHz mono PCM16,
// posted as ArrayBuffers of EXACTLY 1024 bytes (512 samples = 32 ms). Also posts {type:'level'} ~10x/s.
//
// Pipeline per sample: mono mix -> biquad low-pass (anti-alias, state carried across blocks)
// -> linear interpolation at 16 kHz positions (fractional position and previous sample carried
// across process() calls, so nothing is dropped at block edges) -> Float32 -> Int16 with clipping.
const OUT_RATE = 16000;
const FRAME_SAMPLES = 512;

class Pcm16kProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.inRate = sampleRate; // global in AudioWorkletGlobalScope
    this.step = this.inRate / OUT_RATE; // input samples per output sample
    this.pos = 0; // read position of the next output sample, relative to the current block (may be -1..0)
    this.prev = 0; // last filtered sample of the previous block
    this.out = new Int16Array(FRAME_SAMPLES);
    this.n = 0;
    // RBJ biquad low-pass at 7 kHz (below the 8 kHz Nyquist of the output), Q = 0.707
    this.filter = this.inRate > OUT_RATE;
    if (this.filter) {
      const f0 = 7000, q = Math.SQRT1_2;
      const w = (2 * Math.PI * f0) / this.inRate, cw = Math.cos(w), al = Math.sin(w) / (2 * q), a0 = 1 + al;
      this.b0 = (1 - cw) / 2 / a0; this.b1 = (1 - cw) / a0; this.b2 = (1 - cw) / 2 / a0;
      this.a1 = (-2 * cw) / a0; this.a2 = (1 - al) / a0;
      this.x1 = this.x2 = this.y1 = this.y2 = 0;
    }
    this.levelSum = 0;
    this.levelCount = 0;
  }

  emit(v) {
    const c = v > 1 ? 1 : v < -1 ? -1 : v;
    this.out[this.n++] = c < 0 ? c * 0x8000 : c * 0x7fff;
    if (this.n === FRAME_SAMPLES) {
      this.port.postMessage(this.out.buffer, [this.out.buffer]);
      this.out = new Int16Array(FRAME_SAMPLES);
      this.n = 0;
    }
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0 || !input[0]) return true;
    const len = input[0].length;
    const y = new Float32Array(len);
    for (let i = 0; i < len; i++) {
      let x = 0;
      for (let c = 0; c < input.length; c++) x += input[c][i];
      x /= input.length;
      this.levelSum += x * x;
      if (this.filter) {
        const v = this.b0 * x + this.b1 * this.x1 + this.b2 * this.x2 - this.a1 * this.y1 - this.a2 * this.y2;
        this.x2 = this.x1; this.x1 = x; this.y2 = this.y1; this.y1 = v;
        y[i] = v;
      } else {
        y[i] = x;
      }
    }
    // linear interpolation; index -1 means "last sample of the previous block"
    while (this.pos < len - 1) {
      const i0 = Math.floor(this.pos);
      const frac = this.pos - i0;
      const s0 = i0 < 0 ? this.prev : y[i0];
      const s1 = y[i0 + 1];
      this.emit(s0 + (s1 - s0) * frac);
      this.pos += this.step;
    }
    this.pos -= len;
    this.prev = y[len - 1];

    this.levelCount += len;
    if (this.levelCount >= this.inRate / 10) {
      this.port.postMessage({ type: 'level', rms: Math.sqrt(this.levelSum / this.levelCount) });
      this.levelSum = 0;
      this.levelCount = 0;
    }
    return true;
  }
}

registerProcessor('pcm16k', Pcm16kProcessor);
