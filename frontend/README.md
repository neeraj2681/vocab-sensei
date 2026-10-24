# Vocab Sensei frontend

React + TypeScript + Vite. Code is grouped by feature in `src/features/<feature>/`; all backend calls go through
`src/api/`.

## Run locally

```bash
cd frontend
npm ci            # install exact versions from package-lock.json
npm run dev       # http://localhost:5173 (proxies /api to the backend on :8000)
```

## Checks (same as CI)

```bash
npm run lint          # eslint
npm run format:check  # prettier
npm run typecheck     # tsc
npm test              # vitest
npm run build
```
