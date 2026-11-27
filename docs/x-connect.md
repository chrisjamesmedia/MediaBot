# Connect X: what works, what it needs, what it costs

Checked 2026-11-26 against docs.x.com and live requests from the box.

## What works today (no setup)
- **Typing an @handle** on `/start/` step 1, and adding people by @handle, `x.com/…` link or plain name in step 2.
  This is the full path until X sign-in is switched on, and it needs no X account access at all.
- **Bluesky:** "Bring in who I follow on Bluesky" calls Bluesky's public API (`public.api.bsky.app`,
  `app.bsky.graph.getFollows`) straight from the browser. Free, no sign-in, CORS allowed (`access-control-allow-origin: *`).
- **YouTube:** not included. Reading someone's subscriptions needs Google sign-in (OAuth, `youtube.readonly`) plus a
  Google Cloud project and app verification; a channel handle alone gives nothing useful. Add people by name instead.

## Why X sign-in can't be browser-only
X supports OAuth 2.0 authorization code + PKCE, including public clients ("Single page App" type, no secret). But:
- `POST https://api.x.com/2/oauth2/token` answers with **no `Access-Control-Allow-Origin`** header, and its CORS
  preflight (`OPTIONS`) returns **404**. A page on `chrisjamesmedia.github.io` can't read the token response.
- The API itself (`GET https://api.x.com/2/users/me`, `/following`, …) also sends **no CORS headers**.

So a small server is required for both the exchange and the reads. That's `x-connect/` (two Vercel functions).

## How `x-connect/` works
1. `/start/` shows **Connect X and bring in who I follow** (only when `x_connect` is set in `site.yaml`).
   It links to `https://<your-vercel-app>/api/login`.
2. `/api/login` makes a PKCE verifier and state, seals them in a 10-minute HttpOnly cookie, and sends you to
   `https://x.com/i/oauth2/authorize` with **read-only** scopes: `users.read tweet.read follows.read`
   (+ `like.read bookmark.read` unless `READ_LIKES=0`). No `offline.access`, no write scope of any kind.
3. X sends you back to `/api/callback`. It exchanges the code (confidential client, Basic auth), reads:
   - `GET /2/users/me` (your handle and name),
   - `GET /2/users/{id}/following` (up to `MAX_FOLLOWING`, default 1,000),
   - topic labels (X's `context_annotations` and hashtags) from up to 100 recent likes and 100 bookmarks;
     the posts themselves are never kept or shown,
   then **revokes the access** and redirects to `RETURN_URL#x=<data>`. The fragment never reaches any server;
   `/start/` reads it, stores the list in `localStorage` (`mediabot.follows.v1`), clears the URL, and opens step 2
   with "From who you follow" ready to tap. Nothing is stored server-side, and nothing can post, follow or like.

## What Chris needs to do (about 15 minutes)
1. **X developer app** at <https://console.x.com> (sign in as the X account that should own it):
   create an app, open **User authentication settings**, turn on **OAuth 2.0**, choose type
   **Web App, Automated App or Bot** (confidential), permissions **Read**.
   - Callback URI: `https://<project>.vercel.app/api/callback` (exactly, no trailing slash).
   - Website URL: `https://chrisjamesmedia.github.io/MediaBot/`.
   - Copy the **OAuth 2.0 Client ID and Client Secret** (not the API key / OAuth 1.0a pair).
2. **Buy X API credits** in the Developer Console (pay-per-use, no subscription; set a spending limit). X currently
   adds \$20 of free credits on a first purchase.
3. **Vercel:** import the repo as a new project with **Root Directory = `x-connect`** (no build step), then add these
   Environment Variables (Production):

   | Name | Value |
   | --- | --- |
   | `X_CLIENT_ID` | OAuth 2.0 Client ID |
   | `X_CLIENT_SECRET` | OAuth 2.0 Client Secret |
   | `X_CALLBACK_URL` | `https://<project>.vercel.app/api/callback` (same as in the X app) |
   | `RETURN_URL` | `https://chrisjamesmedia.github.io/MediaBot/start/` (later `https://mediabot.news/start/`) |
   | `SESSION_KEY` | any random string of 32+ characters (e.g. `openssl rand -base64 36`) |
   | `MAX_FOLLOWING` | optional, default `1000` (cost cap per connect; max 5000) |
   | `READ_LIKES` | optional, `0` to skip likes/bookmarks topics and their scopes |

   Deploy. The Hobby plan is free for personal use.
4. Set `x_connect: "https://<project>.vercel.app"` in `site.yaml`, rebuild (`build.py --start`) and publish.
   If the domain changes to mediabot.news, update `RETURN_URL`.

## Cost (X API pay-per-use rates, docs.x.com/x-api/getting-started/pricing, 2026-11-26)
Resources are deduplicated per UTC day, so reconnecting the same day is mostly free.

| Per connect | Chris (owns the app: "Owned Reads" \$0.001 each) | Any other reader |
| --- | --- | --- |
| `users/me` | ~\$0.01 | \$0.01 |
| 1,000 accounts followed | \$1.00 | \$10.00 (\$0.010 each) |
| 100 likes + 100 bookmarks (topics) | \$0.20 | up to \$1.00 (\$0.005 per post) |
| **Total** | **≈ \$1.21** | **≈ \$11** (cap with `MAX_FOLLOWING=200` ≈ \$3, or `READ_LIKES=0`) |

Vercel: \$0 on Hobby. GitHub Pages: \$0. Owned-read pricing applies only when the signed-in X account owns the
developer app, so opening "Connect X" to the public costs real money per reader: keep it for Chris, or lower
`MAX_FOLLOWING` first.

## Not done (on purpose)
No X developer app was created, nothing was deployed, and `x_connect` is empty, so the live site shows the
handle path only. The code was exercised locally with fake settings: login builds a correct PKCE authorize URL;
callback handles cancel, a bad or expired state, and a failed exchange (verified against the real token endpoint,
which rejects the fake client), each returning to `/start/` with a plain message.
