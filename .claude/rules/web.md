---
paths:
  - "src/fonti/web/**"
---

# Web UI (FastAPI + Jinja2 + HTMX)

- Keep the local-only protections in `web/app.py`: loopback bind, `TrustedHostMiddleware`
  (DNS rebinding) and the same-origin check on unsafe methods (CSRF).
- Document text and questions are untrusted: rely on Jinja2 autoescaping, never `|safe`,
  `Markup` or `innerHTML` on them.
- Uploads: keep only `Path(filename).name`, check suffix and size, write inside the job folder.
  Files are served by `doc_id` from the index, never by a client-supplied path.
- Every view handles its states: empty index, ingest in progress, abstention, error.
- User-facing text is Italian; keep it accessible (labels, keyboard, focus).
- Go through `service.py`; no SQL or retrieval logic in the web layer.
