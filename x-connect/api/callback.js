// GET /api/callback?code&state -> exchanges the code, reads (only) who the reader follows and the topics of their
// recent likes and bookmarks, revokes the access, and hands the result back to /start/ in the URL fragment
// (#x=<base64url JSON>), which browsers never send to any server. No database, no logs of content, no refresh access.
import { settings, unseal, getCookie, b64url, COOKIE } from "../lib/seal.js";

const API = "https://api.x.com/2";
const clear = `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;

function back(s, frag) {
  return new Response(null, { status: 303, headers: {
    Location: s.returnUrl.split("#")[0] + "#" + frag, "Set-Cookie": clear, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
  } });
}
async function xget(path, access) {
  const r = await fetch(API + path, { headers: { Authorization: "Bearer " + access } });
  if (!r.ok) throw new Error("x " + r.status + " " + path.split("?")[0]);
  return r.json();
}
const basic = (s) => "Basic " + Buffer.from(encodeURIComponent(s.clientId) + ":" + encodeURIComponent(s.clientSecret)).toString("base64");

export async function GET(request) {
  let s;
  try { s = settings(); } catch (e) { return new Response("X connect is not configured: " + e.message, { status: 500 }); }
  const q = new URL(request.url).searchParams;
  if (q.get("error")) return back(s, "x-error=denied");
  const saved = await unseal(getCookie(request, COOKIE), s.sessionKey);
  if (!saved || saved.state !== q.get("state") || !q.get("code") || Date.now() - saved.t > 10 * 60 * 1000) return back(s, "x-error=expired");

  let access = "";
  try {
    const tr = await fetch(API + "/oauth2/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Authorization: basic(s) },
      body: new URLSearchParams({ grant_type: "authorization_code", code: q.get("code"), redirect_uri: s.callback, code_verifier: saved.verifier, client_id: s.clientId }),
    });
    if (!tr.ok) return back(s, "x-error=exchange");
    access = (await tr.json()).access_token;
    if (!access) return back(s, "x-error=exchange");

    const me = (await xget("/users/me?user.fields=username,name", access)).data;
    // Who they follow: up to MAX_FOLLOWING (1,000 per page). Billed per account returned (docs/x-connect.md).
    const following = [];
    let next = "";
    while (following.length < s.maxFollowing) {
      const n = Math.min(1000, s.maxFollowing - following.length);
      const page = await xget(`/users/${me.id}/following?max_results=${n}&user.fields=username,name` + (next ? "&pagination_token=" + encodeURIComponent(next) : ""), access);
      (page.data || []).forEach((u) => following.push([u.username, (u.name || "").slice(0, 80)]));
      next = page.meta && page.meta.next_token;
      if (!next) break;
    }
    // Topics only (never the posts themselves): X's own topic labels on up to 100 recent likes and 100 bookmarks.
    const topics = {};
    if (s.readLikes) {
      for (const path of [`/users/${me.id}/liked_tweets`, `/users/${me.id}/bookmarks`]) {
        try {
          const page = await xget(path + "?max_results=100&tweet.fields=context_annotations,entities", access);
          (page.data || []).forEach((p) => {
            const seen = new Set();
            (p.context_annotations || []).forEach((a) => { const n = a.entity && a.entity.name; if (n && n.length <= 40) seen.add(n); });
            ((p.entities && p.entities.hashtags) || []).forEach((h) => { if (h.tag && h.tag.length <= 30) seen.add("#" + h.tag); });
            seen.forEach((n) => { topics[n] = (topics[n] || 0) + 1; });
          });
        } catch { /* a missing scope or empty list is fine */ }
      }
    }
    const top = Object.entries(topics).filter(([, c]) => c >= 2).sort((a, b) => b[1] - a[1]).slice(0, 20);
    const payload = { v: 1, me: { username: me.username, name: (me.name || "").slice(0, 80) }, following, topics: top };
    return back(s, "x=" + b64url(new TextEncoder().encode(JSON.stringify(payload))));
  } catch {
    return back(s, "x-error=read");
  } finally {
    if (access) {   // give the access back right away; MediaBot never keeps it
      fetch(API + "/oauth2/revoke", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded", Authorization: basic(s) },
        body: new URLSearchParams({ token: access, token_type_hint: "access_token", client_id: s.clientId }) }).catch(() => {});
    }
  }
}
