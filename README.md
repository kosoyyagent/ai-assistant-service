# Private AI Assistant Web Service

A small self-hosted web service that gives each user their own AI assistant —
a private chat with per-user history and context, an admin panel for
managing accounts, and pluggable LLM backends (Yandex AI Studio / Alice AI
out of the box, easy to point at OpenAI-compatible APIs).

Built for companies that want an internal ChatGPT-like tool where user
accounts are managed centrally instead of everyone using their personal
accounts on public services.

## Features

- **Browser chat** — works on desktop and mobile, single-file UI.
- **Per-user history** — every user gets their own dialog context.
- **Admin panel** — create/disable users, reset passwords, view dialogs.
- **Echo mode** — without API keys the service runs a stub responder so you
  can verify the whole interface before connecting a real model.
- **SQLite storage** — zero external dependencies beyond Flask + requests.

| Chat | Admin panel |
|------|-------------|
| ![chat](docs/chat.png) | ![admin](docs/admin.png) |

## Quick start

```bash
pip install -r requirements.txt
python app.py          # -> http://127.0.0.1:5000
```

Default admin: `admin` / `admin123` — change via `ADMIN_PASSWORD` env var
(see `.env.example`).

## Configuration

Copy `.env.example` to `.env` or export the variables:

- `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, `YANDEX_MODEL` — Yandex AI Studio
  credentials. Leave empty to run the built-in echo mode.
- `ADMIN_PASSWORD` — initial admin password (first run only).
- `SECRET_KEY` — Flask session key.
- `SYSTEM_PROMPT` — assistant persona.

## Notes

- The SQLite database (`assist.db`) is created automatically on first run —
  users table plus messages table.
- The admin can read user dialogs — this is a company-tool feature
  (compliance), keep it in mind when deploying.
- Single process, no worker queue — fine for dozens of users; put nginx in
  front for TLS.

## License

MIT — see LICENSE.
