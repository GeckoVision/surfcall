# Voiceover script + edit guide — Gecko demo

Two things live here:
1. **The cut we shipped** — the ~50s neutral, bot-first narration actually produced
   (`gecko-demo.mp4`), with TTS voice and burned subtitles. Use it to reproduce or re-time.
2. **The ~90s edit guide** (below the divider) — the original product-first storyboard with
   per-beat "what to keep" notes for trimming a long Loom recording.

Honest throughout — every claim is real.

## The cut we shipped (neutral, bot-first, ~50s)

Four voiceover beats, **brand-neutral** so the narration sits cleanly over both the landing
page ("Ayuda Venezuela") and the bot ("SOS Venezuela 2026") without naming — and so
contradicting — either:

| # | Segment (footage) | Voiceover |
|---|---|---|
| 1 | Landing page (~0–14s) | *"After Venezuela's earthquakes, finding emergency help shouldn't be hard. It's a Telegram bot for the earthquake response. Ask in plain Spanish, and get clear answers about shelters, water, and missing people."* |
| 2 | Telegram bot chat (~14–31s) | *"Ask how many people are reported missing — it answers from live data. Search for someone by name — real records, in seconds. Ask for the latest news — always current. No app to install, no sign-up. Just help, where people already are."* |
| 3 | Terminal — `gecko` (~31–43s) | *"And behind it: Gecko. Point it at any API's spec, and in seconds it's agent-usable. The agent calls it correctly, first try, with zero integration code."* |
| 4 | Close card (~43–50s) | *"Gecko. Make any API agent-usable. pip install gecko-surf."* |

Subtitles for beats 1–3 are in [`voiceover.srt`](voiceover.srt) (the close card carries its
own on-screen text). The voice is Deepgram TTS (`aura-2-thalia-en`); regenerate a beat with:

```bash
curl -s -X POST "https://api.deepgram.com/v1/speak?model=aura-2-thalia-en&encoding=linear16&container=wav" \
  -H "Authorization: Token $DEEPGRAM_API_KEY" -H "Content-Type: application/json" \
  -d '{"text":"<beat text>"}' -o vo.wav
```

Assembly recipe (segments → voice → subtitles → mux) is in
[README.md](README.md#assembling-the-narrated-cut).

---

### 0:00–0:06 · Title
**On screen:** the landing page (`ayuda-venezuela-wine.vercel.app`) or the Gecko name.
**VO:** *"An AI agent is only as useful as the APIs it can actually call."*

### 0:06–0:16 · The problem
**On screen:** a quick scroll of dense API reference docs, or just the terminal cursor.
**VO:** *"Today, to wire up one API, someone reads the docs, hand-writes a client, sets up the auth — and still can't tell if the agent is calling it right. Days of glue code. For every API."*

### 0:16–0:24 · The turn
**On screen:** terminal — you run the command. *(Keep this moment.)*
**VO:** *"Gecko does it in one line. Point it at any API's OpenAPI —"*

### 0:24–0:34 · Comprehension
**On screen:** the output appears — `comprehended 19 operations → 10 usable` + the add string.
**Cut:** any loading/wait — speed-ramp or jump-cut the output so it snaps in.
**VO:** *"— and in seconds it's agent-usable. Nineteen endpoints comprehended, the auth-gated ones hidden, and a one-click line to drop into Claude."*

### 0:34–0:50 · Claude calls it, first try *(the money shot)*
**On screen:** paste `claude mcp add …` into Claude Code → ask *"find the available pets"* → Claude calls the tool → result.
**Keep:** the question → the tool call → the result. **Cut:** Claude's thinking/typing dead air — trim straight to the call and the answer.
**VO:** *"Paste that one line into Claude. Now ask in plain language… and it picks the right call, fills the parameters, and gets it right the first time. No client. No docs. No guessing."*

### 0:50–0:56 · The bridge
**On screen:** cut to the landing page, then the bot.
**VO:** *"That's the engine. Here's what you build with it."*

### 0:56–1:18 · The bot in the wild
**On screen:** Telegram **@DEV_VEZbot** — three quick questions:
*"¿cuántas personas desaparecidas hay?"* → *"busca a María"* → *"dame las últimas noticias"*.
**Keep:** ~6s each — the question, then the answer appearing. **Cut:** typing, scrolling, anything past 3 questions.
**VO:** *"Ayuda Venezuela — a Spanish-first Telegram bot for the earthquake response. Behind it, Gecko turned a humanitarian API into tools an agent calls correctly, in real time. Built for the hackathon. No integration code."*

### 1:18–1:30 · Close
**On screen:** the Gecko name + `pip install gecko-surf` + the repo URL.
**VO:** *"Gecko. Make any API agent-usable — no integration code."* *(beat)* *"`pip install gecko-surf`."*

---

## Cutting the long Loom to ~90s
The three biggest time-savers:
1. **Terminal output** — speed-ramp 2–4× or jump-cut; nobody needs to watch it stream.
2. **Claude** — trim the thinking/typing to just *the tool call + the answer*.
3. **Bot** — three questions max, ~6s each; cut all typing/scrolling.

## Two re-cuts (same footage, different lead)
- **Build4Venezuela (bot-first, ~60s):** open on the bot (the 0:56 block), *then* a 15s "and it's powered by Gecko" with the terminal clip, then close. Lead with the human story.
- **Gecko pitch (product-first):** the order above — magic first, impact second.

## If you don't want to record the terminal
Swap the 0:16–0:34 footage for `demo/petstore.gif` (or `vhs demo/gecko-demo.tape`). Same beat, cleaner clip.
