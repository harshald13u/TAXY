# Optional: Cloudflare Vision Worker (NOT in use)

The file `cloudflare-worker.js` in this folder is an **optional** backend that proxies image uploads to Claude Vision API for higher-accuracy OCR. **It is not deployed and not needed.**

## Why it's here

Originally built when we considered paid Vision API extraction. The current production app uses **Tesseract.js** (free, client-side OCR — no API key, no backend, no money) instead.

## When to use it

Switch to the Vision Worker only if:
- Tesseract.js accuracy is too low for your users (~70-85% on clean Form 16 photos)
- You're willing to pay ~₹0.04 per image (Claude Haiku) or ~₹0.40 per image (Claude Sonnet)
- You have an Anthropic API key you're comfortable spending against

## How to switch (5 minutes if you decide later)

1. Sign up at https://dash.cloudflare.com/sign-up (free)
2. Workers → Create Worker → name it `taxy-vision` → paste `cloudflare-worker.js`
3. Settings → Variables → Add `ANTHROPIC_API_KEY` (encrypted)
4. In `app/app.html`, replace the Tesseract.js OCR path with a `fetch()` to your Worker URL

The Worker file already has CORS locked to your GitHub Pages origin so randoms can't burn your credits.

## How to delete it

If you're sure you'll never use it: just delete `backend/cloudflare-worker.js` and this file. Won't break anything.
