# AGENTS.md — LEGACY REPO, READ THIS FIRST

This repo is **Oliver-era legacy** (the pre-pivot AI banking-compliance assistant backend: FastAPI + OpenAI Responses API + Supabase). It is **NOT current Olito platform truth**.

- **Do not pattern-match from this code** for current platform work — architecture, conventions, and providers here predate the cutover. Canonical architecture lives in Olito-Labs/olito-brain/ARCHITECTURE.md and Olito-Labs/olito-brain/docs/integrations-matrix.md.
- **This repo is PUBLIC.** Never add secrets, API keys, customer data, or internal context here — not in code, fixtures, issues, or commit messages.
- Last substantive product work was September 2025 (the "minify-backend" commits keeping only the exam, streaming, slidegenerator, and regulatory APIs); 2026 commits are CI hygiene only.
- Repo state reflects its legacy status: `__pycache__` directories with compiled `.pyc` bytecode (cpython-313) and `.DS_Store` files are committed to git.
- **Disposition: public and archived (2026-10-20).** Kept public so people can read and run the prototype. No hosted deployment exists (all Railway deployments are inactive). No new features or refactors.

CI: `.github/workflows/tests.yml` runs pytest on every push (any branch); there is no deploy pipeline in this repo.
