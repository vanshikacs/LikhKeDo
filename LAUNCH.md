# Launch pack: record, post, submit

Deadlines: **posts live by 12:00 IST, 9 Nov** (engagement counts only until the cutoff) · **submit by 18:00 IST, 10 Nov**.
Hashtags on every post: **#GnaniAI #GreatIndianAIInternshipChallenge** · tag Gnani AI's official LinkedIn page and X handle.

Honesty rule for the video (from the project doc): if a verdict is wrong in the take, keep it and say so, or re-record. Never edit a verdict in post. Show one *Not in writing — ask* card and say LikhKeDo refuses to guess.

---

## 1. One Kaggle session, in this order (≈ 2 hours of GPU time)

| # | Step | Command / action | Done when |
|---|---|---|---|
| 1 | Start Evon | Run all cells of `kaggle/evon_server.ipynb` (GPU T4 x2, Internet on) | last cell prints the `.env` lines |
| 2 | Point the app at it | paste those lines into `.env`, restart the backend | `http://localhost:8000/api/health` shows `"evon":"ok"` |
| 3 | Smoke test | `backend\.venv\Scripts\python scripts\smoke_evon.py` | SUMMARY line; test 4 shows 6 verdicts, slowest call < 80 s |
| 4 | Accuracy | `scripts\eval_answer_key.py` then `scripts\eval_answer_key.py --from-audio` | `demo/eval_results*.md` written |
| 5 | Saved demo cases (mode C) | `scripts\seed_demo.py` | `demo/cache/*/report.json` + WAVs; `/api/demo` lists 3 cases |
| 6 | Record (section 2) | while the tunnel is up | two MP4s |
| 7 | Commit the results | `git add demo/cache demo/eval_results* && git commit && git push` | public site can serve mode C |
| 8 | Stop the Kaggle session | — | quota saved |

Before recording: open `http://localhost:5173/?record=1` once (phone-width column, cards highlight as they appear). Speak into the laptop mic from ~30 cm. If you play the pitch from speakers instead, use `/dev/listen` → *Start + play pitch audio* (echo cancellation off).

## 2. The 2–3 minute demo (only verified scenarios)

Everything below was checked against the saved data in `demo/cache/hi_hinglish/report.json` and
`demo/cache/ta_tamil_english/report.json`. The reveal uses the **saved** cases (badge *Saved from a live check*), so
it works without Kaggle; say that aloud. Open `http://localhost:5173/?record=1`.

| Time | Scene | On screen / what to say | What it proves |
|---|---|---|---|
| 0:00–0:15 | Hook | "Papa went to renew an FD. He came back with a 10-year insurance plan." 26,667 mis-selling complaints in FY25 (IRDAI) | the problem |
| 0:15–0:45 | Live captions | Home → हिंदी → consent → **Start listening**. A teammate reads `demo/pitches/hi_hinglish.txt`. Hindi captions appear; *guaranteed*, *pakka* light up | Prisma v3.0 streaming, code-mixed (needs only Gnani) |
| 0:45–0:55 | No mic? | Show **Recall → Or type what was said** for two seconds | works for anyone |
| 0:55–1:45 | The result | Home → **See a demo** → Hindi. Say: "This was saved from a live check with Evon v3.3, a community 4-bit build." Cards: **Different on paper** — "returns guaranteed… बारह percent" vs "Returns are not guaranteed. The illustrated rates of 4% and 8%…" (page 2). **Different on paper** — "सिर्फ पाँच साल premium" vs "…premium paying term of 10 years" (page 1). **Written** — "दस लाख का life cover" vs "Sum assured on death: Rs 10,00,000" (page 1). **Not in writing** — "शून्य percent interest" loan: "the document has no loan clause, so it says *ask*, it doesn't guess." | grounded verdicts with both quotes |
| 1:45–1:55 | Honest label | Point at the grey line under a card: "The verdict and clause are Evon's; this sentence is a standard one, because the 4-bit build garbled Hindi." | transparency |
| 1:55–2:10 | Voice | Tap **सुनिए**: Tarika reads the summary | Timbre v3.0 |
| 2:10–2:25 | Action | **Likh Ke Do slip** (print view), then **30-day free look** | a concrete next step |
| 2:25–2:40 | Proof | **Under the hood**: Prisma request ids, Evon calls (⚡ thinking off), Timbre. "6 promises checked in 17 s" (Hindi case `pipeline_ms` = 17,023) | real Gnani calls |
| 2:40–3:00 | Tamil + close | **See a demo** → Tamil: **Written** "முப்பது நாளுக்குள்ளே… திருப்பி கொடுக்கலாம்" vs "Free-look period… within 30 days" (page 3), and ₹10 lakh **Written**. "On a 30-promise test it scored 20/30 and never wrongly said Written. Jo bola, kya woh likha hai? LikhKeDo." | regional language, honest score |

Do **not** scroll onto these Hindi cards as successes: "पहले कुछ नहीं देना" (rejected by the grounding check: you may show it as
the safety net) and "returns कर सकते हैं" (the free-look promise, extracted badly). Do not show Marathi.

If you run a **live** Evon check on camera instead, keep whatever comes out (verdicts vary run to run) and say so.

## 3. The 60-second cut (Demo Day Drop)

| Time | Beat | Script |
|---|---|---|
| 0–5 s | Hook | Close-up of a bank form. VO: "Papa went to renew an FD." Cut to the policy. "He came back with this." |
| 5–15 s | Problem | RM line, captioned: "Bilkul FD jaisa, returns guaranteed." On screen: 26,667 mis-selling complaints in one year (IRDAI FY25). |
| 15–35 s | Product | Live captions with red chips; tap Check; the two red cards slide in with both quotes. |
| 35–45 s | Gnani reveal | Tarika's Hindi summary plays. Overlay: Prisma v3.0 heard it · Evon v3.3 checked it · Timbre v3.0 said it. |
| 45–55 s | Impact | The Likh Ke Do slip. Text: "Ask for it in writing. Or cancel within 30 days." |
| 55–60 s | Close | "Jo bola, kya woh likha hai?" — LikhKeDo. #GnaniAI |

## 4. Captions for the RM's lines (Hinglish → English subtitle)

| Hinglish (as spoken) | English subtitle |
|---|---|
| Sir, aapki FD agle hafte mature ho rahi hai na… | Sir, your FD matures next week, right… |
| Isme returns guaranteed hain, har saal minimum 12 percent milega. | Returns are guaranteed: at least 12% every year. |
| Aapko sirf 5 saal premium bharna hai, uske baad kuch nahi dena. | You pay premium for only 5 years, nothing after that. |
| Saath mein 10 lakh ka life cover bhi milta hai. | It also comes with ₹10 lakh life cover. |
| Kabhi bhi loan le sakte hain, wo bhi 0 percent interest par. | You can take a loan any time, at 0% interest. |
| Ye FD se to pakka better hai. | It's definitely better than an FD. |
| 30 din ke andar pasand nahi aayi to aap return kar sakte hain. | Don't like it? Return it within 30 days. |
| Bas yahan sign kar dijiye, baaki formalities main dekh lunga. | Just sign here, I'll handle the rest. |

## 5. Posts (from the project doc, updated for what we actually built)

**LinkedIn** (attach the 2–3 min video; fill the brackets):

> My [father / uncle / neighbour] went to the bank to renew an FD. He came back with a 10-year insurance plan he "only had to pay for five years." The paper said ten.
>
> This is common enough that the insurance regulator recorded 26,667 mis-selling complaints against life insurers last year — and those are only the people who knew to complain.
>
> The promise is made out loud, in Hindi or Tamil or Hinglish. The truth is written in English, on page 4. So we built LikhKeDo ("put it in writing").
>
> It listens to the pitch, pulls out every promise, checks each one against the policy's own Customer Information Sheet, and tells you in your language which promises are written down, which are different on paper, and which you should ask to get in writing.
>
> Built for the #GreatIndianAIInternshipChallenge on @Gnani AI's stack:
> • Prisma v3.0 hears code-mixed speech like "returns guaranteed hain" and keeps the English finance words intact (on our synthetic test pitch it kept 93–95% of the words even under heavy background noise)
> • Evon v3.3, which we self-host — on a ₹0 budget, as a community 4-bit build on free GPUs — compares each promise with the document and must quote both sides. If it can't, it says "ask" instead of guessing
> • Timbre v3.0 explains the result slowly, in Hindi, Marathi or Tamil, the way you'd want your parents to hear it
>
> The demo uses a fictional insurer and synthetic voices. It isn't financial advice. Our honest accuracy numbers are in the repo: https://github.com/vanshikacs/LikhKeDo
>
> Has someone in your family been sold a policy they didn't understand? What did the agent say? We'd like to add those phrases to our test set.
>
> #GnaniAI #GreatIndianAIInternshipChallenge

If the full BF16 Evon ran instead, replace the dash clause with nothing. If no Evon run happened before posting, do not post a mode-A video; use the rules-check run and say so.

**X** (attach the 60 s cut):

> Papa went to renew an FD. Came back with a 10-yr insurance plan "you pay only 5 years." The paper said 10.
>
> LikhKeDo listens to the sales pitch in Hindi/Hinglish/Tamil/Marathi, checks every promise against the policy doc, then tells you out loud what isn't written.
>
> Built on @[Gnani's X handle] Prisma + Evon + Timbre 👇 #GnaniAI #GreatIndianAIInternshipChallenge

## 6. Judge questions and truthful answers

| Question | Answer |
|---|---|
| Is this really Evon? | Yes: Gnani's Evon v3.3 30B-A3B weights, as a community 4-bit GGUF (IQ4_XS) on llama.cpp on two free Kaggle T4s. Every report names the engine. We did not run Gnani's BF16 build (no GPU budget). |
| Why are the explanations standard sentences? | The 4-bit file dropped tokens in Hindi even at temperature 0, so its free text was garbled or unsupported by the clause. Evon still picks each promise, verdict and clause; the sentence is labelled as standard on screen. With BF16 on vLLM the code uses the model's explanations. |
| How accurate is it? | 20/30 on our answer key (written before any model run, unchanged), no wrong *Written*, cited clause right in 13/15 correct verdicts. Small, synthetic test set: it shows the pipeline works, not production accuracy. |
| What stops hallucinated clauses? | Code checks every verdict: the promise must be in the transcript, the clause quote in the cited clause (fuzzy ≥ 90), the clause on the same topic (BM25), and every number of a *Written* verdict in the clause. Failures become *Not in writing — ask*. |
| Isn't "not in writing" the same as "false"? | No. It means the document doesn't say it, so ask for it in writing. We never say the seller lied. |
| Why Marathi isn't shown? | Its live run had two wrong *Different on paper* cards. It is documented in the README and the app warns when Marathi is selected. |
| What about privacy? | No accounts or personal IDs; raw audio is never written to disk; case data, cached transcripts and audio are deleted after 24 h or on *Delete my data*; logs carry request ids, not text. |
| Why a saved case in the demo? | The free GPU session is not always on. Saved cases are real live runs, labelled with their date and engine; a live check never silently turns into a saved one. |
| What would you do next? | Run BF16 Evon on the same answer key, grow a native-reviewed test set with real CIS layouts, add OCR. |

## 7. Submission checklist (10 Nov, by 18:00 IST)

- [ ] LinkedIn post live by 12:00 IST 9 Nov, tagging Gnani AI's page, both hashtags, video attached
- [ ] X post live, tagging Gnani's handle, both hashtags
- [ ] Reply to every comment within the hour
- [ ] Public site on Render + Vercel with `DEMO_ONLY=true` serving the saved cases (see DEPLOY.md); opens logged-out
- [ ] Repo public; README accuracy and noise tables filled from real runs
- [ ] Participant workspace: copy title, problem, users, models and the 250-word explanation from SUBMISSION.md; add team contributions
- [ ] Submit: demo video, explanation, models used, the two post links
- [ ] Check logged-out: links open, video plays, posts are public
