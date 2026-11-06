# Test clips for Phase 1

Record 3 short WAV clips of yourself (10–20 s each, never over 30 s) saying a Hinglish insurance pitch.
Name them `clip1.wav`, `clip2.wav`, `clip3.wav`. Use only your own voice and fictional details
(Bharosa Life, Suraksha Plus); no real names, phone numbers or account numbers.

Example lines to mix and match:

- "Sir, ye Suraksha Plus plan hai, isme 12 percent guaranteed returns milte hain, bilkul FD jaisa."
- "Sirf 5 saal premium dena hai, uske baad lock-in nahi hai, jab chahe paisa nikaal lo."
- "Maturity pe poora paisa tax free milega, 80C ka benefit bhi hai."

Any sample rate is fine; the scripts convert to 16 kHz mono. Record in a quiet room.
To convert a phone recording: `ffmpeg -i input.m4a -ac 1 -ar 16000 clip1.wav`
