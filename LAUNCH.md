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

## 2. The 2–3 minute demo (matches the app as built)

Pitch: `demo/pitches/hi_hinglish.txt`, read live by the teammate playing the RM. The fictional insurer is Bharosa Life.

| Time | Scene | On screen / audio | What it proves |
|---|---|---|---|
| 0:00–0:15 | Hook | Text over a bank-desk shot: "Papa went to renew an FD. He came back with a 10-year insurance plan." Then: 26,667 mis-selling complaints last year (IRDAI FY25) | the problem |
| 0:15–0:30 | Setup | Papa opens LikhKeDo, picks हिंदी, ticks consent, taps **Start**. Tarika (Timbre) says in Hindi that the conversation is being noted | consent · Timbre v3.0 |
| 0:30–1:15 | The pitch, live | RM reads the pitch. Hindi captions appear line by line; chips light up: **guaranteed**, **pakka**, **sirf N saal** | Prisma v3.0 streaming, codemix keeps "returns guaranteed", "premium" readable |
| 1:15–1:30 | Check | Tap **Next → sample Bharosa Life document → Check**. Progress: "Checking all 6 promises…" | the pipeline runs |
| 1:30–2:05 | The reveal | Badge **A · Live check · Evon v3.3 …** (say the engine label aloud). Cards: **Different on paper** "returns guaranteed, 12%" vs "Returns are not guaranteed…4% and 8%"; **Different on paper** "only 5 years premium" vs "Premium paying term: 10 years"; **Written** ₹10 lakh cover; **Written** 30-day return (free look); **Not in writing — ask** "loan at 0% interest" and "better than FD" — say: *it refuses to guess* | both quotes side by side, grounded |
| 2:05–2:20 | Voice | Tap **सुनिए**: Tarika reads the summary slowly in Hindi | Timbre v3.0 `<slow>` `<pauses>` |
| 2:20–2:35 | Action | **Likh Ke Do slip** (unwritten promises, signature line), then **Already bought? 30-day free look** | a concrete next step |
| 2:35–2:50 | Proof | Open **Under the hood**: Prisma request ids + detected language, Evon calls (model, thinking off, seconds), Timbre voice + latency. Overlay: "6 promises checked in __ s" (**real number from this take**) | genuine Gnani use |
| 2:50–3:00 | Close | Quick flash of the Tamil saved case (badge C). "Jo bola, kya woh likha hai? LikhKeDo." | regional language |

Say once, plainly: "Evon here is a community 4-bit build of Gnani's Evon v3.3, running on free GPUs" (if that's what ran). Don't claim money saved.

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

## 6. Submission checklist (10 Nov, by 18:00 IST)

- [ ] LinkedIn post live by 12:00 IST 9 Nov, tagging Gnani AI's page, both hashtags, video attached
- [ ] X post live, tagging Gnani's handle, both hashtags
- [ ] Reply to every comment within the hour
- [ ] Public site on Render + Vercel with `DEMO_ONLY=true` serving the saved cases (see DEPLOY.md); opens logged-out
- [ ] Repo public; README accuracy and noise tables filled from real runs
- [ ] Participant workspace: copy title, problem, users, models and the 250-word explanation from SUBMISSION.md; add team contributions
- [ ] Submit: demo video, explanation, models used, the two post links
- [ ] Check logged-out: links open, video plays, posts are public
