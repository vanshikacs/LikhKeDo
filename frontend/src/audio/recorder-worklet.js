// AudioWorklet: mic audio (any sample rate) -> 16 kHz mono PCM16, posted as exactly 1024-byte chunks.
class Pcm16kProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000; // sampleRate is a global in AudioWorkletGlobalScope
    this.t = 0;                       // fractional read position inside the current block
    this.out = new Int16Array(512);   // 512 samples * 2 bytes = 1024 bytes
    this.n = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0 || !input[0]) return true;
    const len = input[0].length;
    let mono = input[0];
    if (input.length > 1) {
      mono = new Float32Array(len);
      for (let c = 0; c < input.length; c++) for (let i = 0; i < len; i++) mono[i] += input[c][i] / input.length;
    }
    while (this.t < len) {
      // average the input samples that fall into this output sample (simple anti-aliasing)
      const start = Math.floor(this.t);
      const end = Math.min(len, Math.max(start + 1, Math.floor(this.t + this.ratio)));
      let sum = 0;
      for (let k = start; k < end; k++) sum += mono[k];
      const v = Math.max(-1, Math.min(1, sum / (end - start)));
      this.out[this.n++] = v < 0 ? v * 0x8000 : v * 0x7fff;
      if (this.n === 512) {
        this.port.postMessage(this.out.buffer, [this.out.buffer]);
        this.out = new Int16Array(512);
        this.n = 0;
      }
      this.t += this.ratio;
    }
    this.t -= len;
    return true;
  }
}

registerProcessor('pcm16k', Pcm16kProcessor);
