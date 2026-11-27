# Private X follows import (free, no X API)

Brings a reader's X follow list into /start/ and /profile/ without a login, a server or any cost. The list never touches the public repo or the built site.

## Two ways in
1. **One-tap link**: `<site>/start/#xf=z<base64url(deflate-raw JSON)>` (or `#xf=j<base64url JSON>` uncompressed). It is a URL *fragment*, so browsers never send it to a server. The page reads it, stores it, and removes it from the address bar. Opening a link on a page that is already open also works (hashchange).
2. **File or paste**: on /start/ step 1 or /profile/ ("Import my X follows"): paste a link, paste JSON, or choose a `.json` file.

## Accepted JSON
* Link payload: `{"v":1,"me":"handle","f":[[handle,name,followers,bucket]],"ch":[[handle,name,followers,weight,follows]]}`. `bucket` 0..4 = AI & tech, Investing, Science & health, Culture & ideas, Other.
* File: `{"follows":[{"handle","name","followers","bucket":"ai_tech|investing|science_health|culture|other"}],"crowdhealth":[{"handle","name","followers","weight","follows"}]}`.
* A raw X API reply `{"data":[{"username","name","public_metrics"}]}` also works (everything lands in Other).

## What it does
* Saves rows into `mediabot.follows.v1` as `x: [[handle, name, followers, bucket]]` and, if given, `x_crowd: [[handle, name, followers, weight, follows]]`.
* Preselects people (weight Normal): the 40 biggest accounts outside Investing. The optional group (`ch`) is preselected with its own weights and sits at the top. Everything else is under "More from who you follow", collapsed, with group chips and search.
* Sets the reader's X handle if empty (`me`). It never marks X as "connected".

## Making a link (keep the output OUTSIDE the repo)
`python3 tools/x_follows_link.py follows.json ~/private-out --me handle [--group group.json]` writes `x-follows-link.txt` and `mediabot-x-follows-import.json`. About 11 KB compressed for 550 follows.

Never commit follow lists, links or import files. `.gitignore` blocks the usual names.
