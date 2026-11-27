# x-connect (optional, not deployed)

A two-function Vercel backend that lets MediaBot's `/start/` page offer **Connect X and bring in who I follow**.
X's OAuth and API endpoints send no CORS headers, so a static GitHub Pages site can't do this alone.

- `GET /api/login`: redirects to X's consent screen (read-only scopes).
- `GET /api/callback`: exchanges the code, reads who you follow plus topic labels from recent likes and bookmarks,
  revokes the access, and returns to `/start/#x=…`. Nothing is stored server-side.

Setup, costs and the exact env vars: [docs/x-connect.md](../docs/x-connect.md).
