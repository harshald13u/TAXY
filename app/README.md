# Taxy

Two files. That's the whole app right now.

## Open these (double-click)

**`index.html`** — the homepage. This is what users land on. Hero, features, demo of the chat, pricing, FAQ.

**`app.html`** — the actual app. Chat-based ITR filing. Drop documents, AI does the work.

## What changed since last time

- Renamed: Karya → **Taxy**
- All CSS is **inline** now — no Tailwind dependency. The previous version broke when the CDN didn't load. This won't.
- Aesthetic: serious dark mode. Linear/Vercel-quality. Deep `#0a0a0b` background, subtle purple-to-pink accent gradient, Inter font with serif italic flourish for emphasis.
- Homepage has a real visual identity now.

## What works

In `app.html`, click **"Demo with sample data"** to see the full flow:
- AI reads three demo documents with progress indicators
- Extracts salary, HRA, employer NPS
- Recognises last year's pattern ("you claimed HRA / 80C / 80D last year")
- Asks only the questions it can't figure out
- Computes both regimes
- Shows recommendation with savings
- Generates downloadable ITR-1 JSON in DRAFT structure (modelled on CBDT schema for AY 2027-28; pending official notification)

In `index.html`:
- Hero with the chat preview embedded
- Feature grid (6 cards)
- Real comparison block ("Priya saved ₹36,587" — engine-computed)
- 3-tier pricing
- FAQ
- Final CTA

## What doesn't work yet

- Real document parsing (Claude API integration needs backend)
- User auth, payments, database
- Direct e-filing via ERI
- Capital gains, business income flows

## Brand snapshot

- **Name:** Taxy
- **Tagline:** "Your taxes, just a conversation."
- **Colors:** `#0a0a0b` background, `#a855f7 → #ec4899` accent gradient, `#fafafa` text
- **Type:** Inter (body), Instrument Serif italic (display flourish)

## Next session — pick one

**A.** Connect a real Claude API backend so document parsing actually works on real PDFs.

**B.** Add the capital gains / ITR-2 conversation flow.

**C.** Build the multi-year memory layer so it actually compares past returns to current docs.

**D.** Founder pitch deck (10-12 slides) for investor / co-founder conversations.

**E.** Set up the real Next.js + FastAPI project structure for handing to a developer.

Tell me. We'll build it.
