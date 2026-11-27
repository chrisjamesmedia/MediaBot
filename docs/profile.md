# Reader profile (`mediabot.profile.v1`)

Made by `/start/` (onboarding, four short steps) and edited on `/profile/`. It lives **only in the reader's
browser** (`localStorage`), so the public repo and site never hold anyone's people or topics. It contains no keys,
passwords or X access of any kind.

The guiding order, from Chris: **people first, then topics, then fun** (jokes, memes, a game pick, a movie pick, a poem).

## Storage keys

| Key | What | Written by |
| --- | --- | --- |
| `mediabot.profile.v1` | The profile below (JSON) | `/start/`, `/profile/` |
| `mediabot.follows.v1` | Optional pick-list brought in from X or Bluesky: `{ "x": [[handle, name, followers?, bucket?], …], "x_crowd": [[handle, name, followers, weight, follows], …], "x_topics": [label, …], "x_at": ISO, "bluesky": [[handle, name], …], "bluesky_at": ISO }`. Only used to pre-fill People; not part of the profile. | `/start/`, `/profile/` |
| `mediabot.start.step` (sessionStorage) | Which onboarding step was open | `/start/` |

Quick Create's own keys (xAI key, saved papers) are separate; this profile never stores the xAI key.

## Shape (v1)

Full JSON Schema: [`profile.schema.json`](profile.schema.json).

```json
{
  "version": 1,
  "updated": "2026-11-27T02:11:54.095Z",
  "onboarded": true,
  "accounts": { "x": { "handle": "yourname", "connected": false, "imported": "" }, "bluesky": { "handle": "" } },
  "people": [
    { "name": "", "handle": "Rainmaker1973", "platform": "x", "weight": 3, "from": "you" },
    { "name": "Mary Oliver", "handle": "", "platform": "web", "weight": 1, "from": "you" }
  ],
  "topics": [ { "label": "Nature", "weight": 3, "from": "preset" }, { "label": "Birdwatching", "weight": 2, "from": "you" } ],
  "fun": { "jokes": true, "memes": false, "game": false, "movie": true, "poem": true },
  "priority": ["people", "topics", "fun"]
}
```

- **Weights** are three plain words, stored as numbers: `1` = A little, `2` = Normal (default), `3` = A lot.
  Never show a number or "up to N" to the reader.
- `platform: "web"` is a person given by name only (no handle): look for their writing anywhere.
- Fun defaults for a new profile: jokes and poem on, the rest off.

## Using it (Quick Create, daily papers)

Include `assets/profile.js` (no dependencies) and use `window.MediaBotProfile`:

```js
var p = MediaBotProfile.load();          // normalized profile, or null if the reader has none
if (p) {
  MediaBotProfile.brief(p);   // plain-text brief for Grok: people by weight, then topics, then the fun picks
  MediaBotProfile.mix(p);     // suggested share of items, e.g. {people: 50, topics: 30, fun: 20} (percent)
}
```

Without the script, read `JSON.parse(localStorage.getItem("mediabot.profile.v1"))` and treat unknown or missing
fields as their defaults (`MediaBotProfile.normalize` does exactly that).

How a generator should use the weights:
1. **Order:** people section first, topics second, fun last (`priority`).
2. **Share of items:** people get the largest share, then topics, then one short fun block. `mix()` gives a starting split.
3. **Within a section:** "A lot" ≈ 3 times the room of "A little", "Normal" ≈ 2 times. With more people than room,
   take every "A lot", then "Normal", then "A little", rotating day to day so nobody is starved.
4. **x handles** → X `from:` searches (`x_search` `allowed_x_handles`, max 10 per call); **bluesky** handles and
   **web** names → web search. Keep the existing rules: real, linked posts only; fun items real and credited.

The daily routine can't read a browser's localStorage. To feed the daily papers, export the profile JSON (e.g. a future
"Copy my profile" button or the reader pasting it) into `papers/<slug>/profile.json` on the box. Keep that file out of
the public repo (add it to `.gitignore` first), since it lists who the reader follows.
