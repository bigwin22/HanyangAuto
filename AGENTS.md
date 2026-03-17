# Repository Guidelines

## Project Structure & Module Organization
HanyangAuto is now **Chrome extension-first**.

- `chrome_extension/`: primary product (MV3 extension: `manifest.json`, `background.js`, `content_script.js`, `popup.*`).
- `automation/`: legacy Selenium automation worker exposed as FastAPI (`main.py`).
- `back/`: legacy core API (user/admin endpoints, DB/log access).
- `front/`: legacy web app (`front/web` for Vite + React client, `front/main.py` for FastAPI proxy/static serving).
- `utils/`: shared modules (`database.py`, `logger.py`, Selenium helpers).

## Build, Test, and Development Commands
From repository root:

- `docker compose up --build`: build and run `front`, `back`, `automation` together.
- `bash genkey.sh`: generate encryption key file used by DB/password encryption.
- `uvicorn back.main:app --reload --port 9000` (local backend dev).
- `uvicorn automation.main:app --reload --port 7000` (local automation worker).
- `cd front/web && npm install && npm run dev`: run legacy React UI locally.
- `cd front/web && npm run build && npm run test && npm run typecheck`: production build + Vitest + TS checks.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` for functions/variables, explicit typing where practical.
- JS/TS: Prettier-formatted, 2-space indentation, `camelCase` for variables/functions, `PascalCase` for React components (e.g., `Dashboard.tsx`).
- Keep selectors/constants centralized for LMS automation logic; avoid hardcoding duplicates across extension files.

## Testing Guidelines
- Current automated tests exist mainly in `front/web` via Vitest (`npm run test`).
- Add unit tests as `*.test.ts(x)` alongside or near tested modules.
- For extension changes, include manual verification steps: login, course discovery, lecture completion, and stop/restart behavior on `https://learning.hanyang.ac.kr`.

## Commit & Pull Request Guidelines
- Recent history favors concise, imperative summaries (English or Korean). Prefer: `Add ...`, `Refactor ...`, `Fix ...`.
- Avoid vague subjects like `init` or `ignore`; keep one logical change per commit.
- PRs should include:
  - what changed and why,
  - impacted modules (`chrome_extension`, `back`, etc.),
  - test evidence (command output or manual scenario checklist),
  - screenshots/GIFs for popup/UI behavior changes.
