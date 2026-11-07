// Fails if any hi/mr/ta UI string contains a run of 3+ Latin-script words (an English sentence leaking in),
// or if a language is missing a key. Product names and common loan words are allowed.
// Run: node scripts/check-i18n.mjs   (runs before every `npm run build`)
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const src = readFileSync(fileURLToPath(new URL('../src/lib/i18n.ts', import.meta.url)), 'utf8')
const ALLOW = ['Suraksha Plus Guaranteed Wealth Plan', 'Bharosa Life', 'Likh Ke Do', 'LikhKeDo', 'free look', 'free-look',
  'lock-in', 'premium', 'loan', 'FD', 'ULIP', 'PDF', 'CIS', 'Chrome', 'Edge', 'Safari', 'GPU', 'Evon']
const RUN = /[A-Za-z][A-Za-z'’]*(?:[\s,.-]+[A-Za-z][A-Za-z'’]*){2,}/g
const ENTRY = /\n {2}(\w+):\s*\n?\s*'((?:[^'\\]|\\.)*)'/g
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\-]/g, '\\$&')

function block(name, header) {
  const start = src.indexOf(header)
  if (start < 0) throw new Error(`no block for ${name}`)
  return src.slice(start, src.indexOf('\n}\n', start))
}
const keys = (b) => new Set([...b.matchAll(/\n {2}(\w+):/g)].map((m) => m[1]))

let bad = 0
const en = keys(block('en', 'const en = {'))
for (const lang of ['hi', 'mr', 'ta']) {
  const b = block(lang, `const ${lang}: Strings = {`)
  for (const m of b.matchAll(ENTRY)) {
    let text = m[2].replace(/\\n/g, ' ').replace(/\{\w+\}/g, ' ').replace(/\b[A-Z][A-Z_]{2,}\b/g, ' ')
    for (const a of [...ALLOW].sort((x, y) => y.length - x.length)) text = text.replace(new RegExp(escapeRe(a), 'gi'), ' ')
    const runs = text.match(RUN)
    if (runs) {
      bad++
      console.error(`${lang}.${m[1]}: English run ${JSON.stringify(runs)}`)
    }
  }
  const have = keys(b)
  for (const k of en)
    if (!have.has(k)) {
      bad++
      console.error(`${lang}: missing key ${k}`)
    }
}
if (bad) {
  console.error(`check-i18n: ${bad} problem(s)`)
  process.exit(1)
}
console.log(`check-i18n: OK (${en.size} keys x 4 languages, no English runs in hi/mr/ta)`)
