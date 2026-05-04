/**
 * Taxy Vision API — Cloudflare Worker proxy.
 *
 * Frontend posts a base64-encoded image; this Worker forwards it to Anthropic's
 * Claude Vision endpoint with a strict JSON-extraction prompt, then returns the
 * parsed Form 16 fields. Your ANTHROPIC_API_KEY never leaves the Worker.
 *
 * ────────────────────────────────────────────────────────────────────
 * DEPLOY IN 5 MINUTES (free tier — 100k requests/day):
 *
 * 1. Create a free Cloudflare account → https://dash.cloudflare.com/sign-up
 * 2. Workers → "Create Worker" → name it "taxy-vision"
 * 3. Click "Edit code" → paste this entire file → Save and Deploy
 * 4. Settings → Variables → "Add variable":
 *      Name:   ANTHROPIC_API_KEY
 *      Value:  sk-ant-...   (get one at console.anthropic.com)
 *      Encrypt: ✓
 * 5. Settings → Triggers → note the Worker URL (e.g. https://taxy-vision.<you>.workers.dev)
 *
 * 6. In app/app.html change the line:
 *      const VISION_API_ENDPOINT = '/api/parse-image';
 *    to:
 *      const VISION_API_ENDPOINT = 'https://taxy-vision.<you>.workers.dev/';
 *
 * 7. Add your GitHub Pages URL to ALLOWED_ORIGINS below, redeploy Worker.
 *
 * Cost: Claude Haiku Vision ≈ $0.0005/image (~₹0.04). Sonnet ≈ $0.005/image (~₹0.40).
 * ────────────────────────────────────────────────────────────────────
 */

const ALLOWED_ORIGINS = [
  'https://harshald13u.github.io',
  // 'http://localhost:8000',  // uncomment for local testing
];

const MODEL = 'claude-haiku-4-5-20251001';      // cheap + fast. Use 'claude-sonnet-4-6' for higher accuracy.
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;       // 10 MB

const EXTRACTION_PROMPT = `You are extracting structured data from an Indian Form 16 (TDS certificate) image.

Return STRICT JSON with this exact schema (no commentary, no markdown):
{
  "employer": "<employer name as printed>",
  "pan": "<10-character PAN of employee>",
  "salary": <gross salary as integer rupees>,
  "hra": <house rent allowance as integer rupees>,
  "tdsPaid": <total TDS deducted as integer rupees>,
  "sec80c": <Section 80C deduction claimed as integer rupees, or 0>,
  "sec80d": <Section 80D health insurance deduction as integer rupees, or 0>,
  "confidence": {
    "employer": "high|medium|low",
    "pan": "high|medium|low",
    "salary": "high|medium|low",
    "hra": "high|medium|low",
    "tdsPaid": "high|medium|low"
  }
}

Rules:
- If a field isn't visible or is unreadable, use null and confidence "low".
- Strip commas/spaces from numbers. "₹18,50,000" becomes 1850000.
- PAN format is 5 letters + 4 digits + 1 letter. Reject anything else as null.
- If this image is NOT an Indian Form 16, return: {"error":"not_form16","text":"This doesn't look like a Form 16. Please upload a Form 16 PDF or image, or type the values manually."}
- Return JSON only. No prose.`;


export default {
  async fetch(request, env) {
    // === CORS preflight ===
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    if (request.method !== 'POST') {
      return json({ error: 'method', text: 'Use POST' }, 405, request);
    }

    // === Parse + validate input ===
    let body;
    try { body = await request.json(); }
    catch { return json({ error: 'bad_json', text: 'Invalid JSON body' }, 400, request); }

    const { image, mimeType } = body || {};
    if (!image || typeof image !== 'string') {
      return json({ error: 'no_image', text: 'Missing image' }, 400, request);
    }
    // base64 length × 0.75 ≈ raw bytes
    if (image.length * 0.75 > MAX_IMAGE_BYTES) {
      return json({ error: 'too_large', text: 'Image > 10 MB. Compress and retry.' }, 413, request);
    }
    const mt = (mimeType || 'image/png').toLowerCase();
    if (!['image/jpeg', 'image/jpg', 'image/png', 'image/webp'].includes(mt)) {
      return json({ error: 'bad_mime', text: 'Use JPG, PNG, or WEBP.' }, 400, request);
    }

    if (!env.ANTHROPIC_API_KEY) {
      return json({ error: 'config', text: 'Backend missing ANTHROPIC_API_KEY env var. Worker owner: see deploy steps in this file.' }, 500, request);
    }

    // === Call Claude Vision ===
    let claudeRes;
    try {
      claudeRes = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'x-api-key': env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01',
          'content-type': 'application/json',
        },
        body: JSON.stringify({
          model: MODEL,
          max_tokens: 1024,
          messages: [{
            role: 'user',
            content: [
              { type: 'image', source: { type: 'base64', media_type: mt === 'image/jpg' ? 'image/jpeg' : mt, data: image } },
              { type: 'text', text: EXTRACTION_PROMPT },
            ],
          }],
        }),
      });
    } catch (e) {
      return json({ error: 'upstream', text: 'Could not reach Anthropic API: ' + e.message }, 502, request);
    }

    if (!claudeRes.ok) {
      const errText = await claudeRes.text().catch(() => '');
      return json({ error: 'anthropic_' + claudeRes.status, text: 'Anthropic returned ' + claudeRes.status + ': ' + errText.slice(0, 200) }, 502, request);
    }

    const claudeJson = await claudeRes.json().catch(() => null);
    if (!claudeJson || !claudeJson.content || !claudeJson.content[0] || !claudeJson.content[0].text) {
      return json({ error: 'bad_response', text: 'Unexpected response shape from Claude.' }, 502, request);
    }

    // === Parse Claude's JSON output ===
    const raw = claudeJson.content[0].text.trim();
    // Sometimes models wrap in ```json ... ``` — strip
    const cleaned = raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim();
    let parsed;
    try { parsed = JSON.parse(cleaned); }
    catch {
      return json({ error: 'parse', text: 'Claude returned non-JSON: ' + raw.slice(0, 200) }, 502, request);
    }

    if (parsed.error) return json(parsed, 200, request);

    // Wrap in {data: ...} so frontend's mapVisionOutputToForm16 can consume both shapes
    return json({ data: parsed }, 200, request);
  },
};


// ────────────────── helpers ──────────────────

function corsHeaders(request) {
  const origin = request.headers.get('Origin') || '';
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allowed,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

function json(obj, status, request) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...corsHeaders(request),
    },
  });
}
