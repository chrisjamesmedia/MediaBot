// Optional proxy for Quick Create (Cloudflare Worker). Only needed if a browser blocks direct calls to api.x.ai.
// It is NOT deployed by this repo. It forwards one endpoint (POST /v1/responses) to api.x.ai and adds CORS headers.
//
// Key handling, in order:
//   1. If the request carries "Authorization: Bearer <key>" (the reader's own key from Quick Create), that key is used.
//   2. Otherwise, only if ALLOW_SERVER_KEY="1" AND the request's Origin equals ALLOWED_ORIGIN, the secret XAI_API_KEY is used.
// Nothing is logged or stored. Only web_search and x_search tools are allowed, so this can't be used as a general relay.

const UPSTREAM = "https://api.x.ai/v1/responses";
const ALLOWED_TOOLS = new Set(["web_search", "x_search"]);
const ALLOWED_FIELDS = new Set(["model", "input", "tools", "max_output_tokens"]);
const MAX_BODY = 64 * 1024;

function cors(origin, env) {
  const allowed = env.ALLOWED_ORIGIN || "https://chrisjamesmedia.github.io";
  return {
    "Access-Control-Allow-Origin": origin === allowed ? origin : allowed,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}
const json = (status, obj, headers) => new Response(JSON.stringify(obj), { status, headers: { ...headers, "Content-Type": "application/json" } });

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowed = env.ALLOWED_ORIGIN || "https://chrisjamesmedia.github.io";
    const h = cors(origin, env);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: h });
    if (request.method !== "POST") return json(405, { error: { message: "POST only" } }, h);
    if (origin !== allowed) return json(403, { error: { message: "Origin not allowed" } }, h);

    const raw = await request.text();
    if (raw.length > MAX_BODY) return json(413, { error: { message: "Request too large" } }, h);
    let body;
    try { body = JSON.parse(raw); } catch { return json(400, { error: { message: "Invalid JSON" } }, h); }
    if (!body || typeof body !== "object" || Object.keys(body).some((k) => !ALLOWED_FIELDS.has(k))) return json(400, { error: { message: "Unsupported field" } }, h);
    if (!Array.isArray(body.tools) || body.tools.some((t) => !t || !ALLOWED_TOOLS.has(t.type))) return json(400, { error: { message: "Only web_search and x_search tools are allowed" } }, h);

    let auth = request.headers.get("Authorization") || "";
    if (!/^Bearer\s+\S+/.test(auth)) {
      if (env.ALLOW_SERVER_KEY === "1" && env.XAI_API_KEY) auth = "Bearer " + env.XAI_API_KEY;
      else return json(401, { error: { message: "Missing API key" } }, h);
    }
    const up = await fetch(UPSTREAM, { method: "POST", headers: { "Content-Type": "application/json", Authorization: auth }, body: JSON.stringify(body) });
    return new Response(up.body, { status: up.status, headers: { ...h, "Content-Type": up.headers.get("Content-Type") || "application/json" } });
  },
};
