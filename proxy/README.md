# Quick Create proxy (optional, not deployed)

Quick Create calls `https://api.x.ai/v1/responses` straight from the browser with the reader's own xAI key.
As of 2026-11-26, api.x.ai answers CORS preflights with `access-control-allow-origin: *` for both `/v1/responses`
and `/v1/chat/completions`, so **no proxy is needed today**. If xAI ever blocks browser calls (some reports said it did
in March 2026 and later reversed), or you want to keep the key out of the browser, deploy this tiny proxy and paste its
URL into Quick Create → "Grok key and connection" → "Optional proxy URL".

## What it does
- `POST /` with the same JSON body Quick Create would send to api.x.ai (`model`, `input`, `tools`, `max_output_tokens`).
- Forwards to `https://api.x.ai/v1/responses` and returns the response with CORS headers for `ALLOWED_ORIGIN` only.
- Allows only `web_search` and `x_search` tools and a 64 KB body, so it can't be used as a general relay.
- Uses the `Authorization: Bearer …` header the page sends. Only if `ALLOW_SERVER_KEY=1` and a secret `XAI_API_KEY` is set
  does it fall back to its own key, and only for requests from `ALLOWED_ORIGIN`.
- Stores and logs nothing.

## Deploy (Cloudflare Workers) when you want it
    cd proxy
    npx wrangler deploy                      # uses wrangler.toml
    # optional server-side key instead of the reader's key:
    npx wrangler secret put XAI_API_KEY      # then set ALLOW_SERVER_KEY = "1" in wrangler.toml and redeploy

Then copy the `https://<name>.<account>.workers.dev` URL into Quick Create. (Quick Create's Content-Security-Policy
allows `*.workers.dev` and `*.vercel.app`; for another host, add it to `connect-src` in `templates/create.html.j2`.)

Only the Cloudflare Worker version is provided. The handler uses the plain Fetch API, so porting it to a Vercel Edge Function is a few lines.
