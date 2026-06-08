# Frontend (Next.js)

Scaffolded separately so it stays a clean, standard Next.js app. From this folder:

```bash
npx create-next-app@latest . --ts --tailwind --app --eslint
# then add shadcn/ui:
npx shadcn@latest init
```

The UI talks to the FastAPI backend (default `http://localhost:8000`). Keep the
response types in sync with the backend's Pydantic schemas. Built by the
`frontend-dev` subagent — see `.claude/agents/frontend-dev.md`.
