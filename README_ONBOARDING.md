### What I need from you (fast path for 49 projects)

1) Fill the CSVs in this folder:
- `PROJECTS_MANIFEST.csv`: one row per project (id, type, repo URL, priority, deploy target)
- `PLAYWRIGHT_TESTS.csv`: only for projects that need E2E tests
- `WEBHOOKS.csv`: only for projects that expose/consume webhooks
- `HTML_SITES.csv`: only for static/marketing sites
- `APPS.csv`: only for app/package releases

2) Drop secrets safely (do not commit real secrets anywhere else):
- Create `secrets/<project_id>/.env` using `CREDENTIALS_SAMPLE.env` as a guide
- Include provider tokens as needed: `VERCEL_TOKEN`, `NETLIFY_AUTH_TOKEN`, `AWS_*`, webhook signing secrets, test user creds

3) Give repo access:
- Best: ensure each `repo_url` is accessible from this environment (public or you provide a GitHub token)
- If private, add a GitHub token (classic or fine-grained) with repo read/write to: `secrets/global/.env` (create it) with `GITHUB_TOKEN=...`
- Or upload ZIPs of the repos into `/workspace/imports/`

4) Assets and copy:
- Put site copy under `content/<project_id>/`
- Put images/assets under `assets/<project_id>/`

5) Priorities and deadlines:
- Set `priority` in `PROJECTS_MANIFEST.csv` (P0, P1, P2) and add any due dates in `notes`

6) Domains and deploy targets:
- For sites/apps: specify `domain` and `deploy_target` (vercel|netlify|s3|gh-pages|app-store|play-store|npm|pypi)
- Provide DNS/Store access if needed (can be in `secrets/<project_id>/.env`)

### After you fill these
- Tell me “kickoff” and I’ll ingest, clone repos, scaffold missing pieces, wire Playwright, configure CI, set up deploys, and run the first full pass.
- You can add more rows anytime; I’ll pick them up.