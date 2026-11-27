// Small helpers: base64url, PKCE, and an AES-GCM sealed cookie (so the server keeps no state at all).
const enc = new TextEncoder(), dec = new TextDecoder();

export function b64url(bytes) {
  return Buffer.from(bytes).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
export function fromB64url(s) { return new Uint8Array(Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64")); }
export function randomString(n = 32) { return b64url(crypto.getRandomValues(new Uint8Array(n))); }
export async function pkceChallenge(verifier) {
  return b64url(new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(verifier))));
}

async function key(passphrase) {
  if (!passphrase || passphrase.length < 32) throw new Error("SESSION_KEY must be at least 32 characters");
  const raw = await crypto.subtle.digest("SHA-256", enc.encode(passphrase));
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}
export async function seal(obj, passphrase) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await key(passphrase), enc.encode(JSON.stringify(obj))));
  return b64url(iv) + "." + b64url(ct);
}
export async function unseal(s, passphrase) {
  try {
    const [iv, ct] = String(s || "").split(".");
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: fromB64url(iv) }, await key(passphrase), fromB64url(ct));
    return JSON.parse(dec.decode(pt));
  } catch { return null; }
}
export function getCookie(request, name) {
  const m = (request.headers.get("cookie") || "").split(/;\s*/).find((c) => c.startsWith(name + "="));
  return m ? decodeURIComponent(m.slice(name.length + 1)) : "";
}

// Settings from environment variables (docs/x-connect.md). Throws if something required is missing.
export function settings(env = process.env) {
  const need = ["X_CLIENT_ID", "X_CLIENT_SECRET", "X_CALLBACK_URL", "RETURN_URL", "SESSION_KEY"];
  const missing = need.filter((k) => !env[k]);
  if (missing.length) throw new Error("Missing environment variables: " + missing.join(", "));
  return {
    clientId: env.X_CLIENT_ID, clientSecret: env.X_CLIENT_SECRET, callback: env.X_CALLBACK_URL,
    returnUrl: env.RETURN_URL, sessionKey: env.SESSION_KEY,
    maxFollowing: Math.max(0, Math.min(5000, parseInt(env.MAX_FOLLOWING || "1000", 10) || 0)),
    readLikes: env.READ_LIKES !== "0",
  };
}
export const COOKIE = "__Host-mbx";
