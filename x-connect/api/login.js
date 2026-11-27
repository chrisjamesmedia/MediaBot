// GET /api/login -> sends the reader to X's consent screen (OAuth 2.0 authorization code + PKCE).
// Read-only scopes only. The PKCE verifier and state ride in a sealed, HttpOnly, 10-minute cookie; nothing is stored.
import { settings, randomString, pkceChallenge, seal, COOKIE } from "../lib/seal.js";

export async function GET() {
  let s;
  try { s = settings(); } catch (e) { return new Response("X connect is not configured: " + e.message, { status: 500 }); }
  const state = randomString(16), verifier = randomString(48);
  const scopes = ["users.read", "tweet.read", "follows.read"].concat(s.readLikes ? ["like.read", "bookmark.read"] : []);
  const u = new URL("https://x.com/i/oauth2/authorize");
  u.search = new URLSearchParams({
    response_type: "code", client_id: s.clientId, redirect_uri: s.callback, scope: scopes.join(" "),
    state, code_challenge: await pkceChallenge(verifier), code_challenge_method: "S256",
  }).toString();
  const cookie = await seal({ state, verifier, t: Date.now() }, s.sessionKey);
  return new Response(null, { status: 302, headers: {
    Location: u.toString(), "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
    "Set-Cookie": `${COOKIE}=${encodeURIComponent(cookie)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
  } });
}
