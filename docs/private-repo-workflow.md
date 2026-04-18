# Private Repo Branching & PR Workflow

This repository is now mirrored into the private `Methodician/Hermes` repo.
Use the following lightweight workflow for future changes:

## 1) Create a feature branch

```bash
git checkout main
git pull origin main
git checkout -b fix/short-description
```

Branch naming conventions:
- `fix/...` for bug fixes
- `feat/...` for new features
- `docs/...` for documentation
- `test/...` for test-only changes
- `refactor/...` for non-behavioral cleanup

## 2) Commit with a conventional message

```bash
git add .
git commit -m "fix(scope): short description"
```

## 3) Push the branch to the private repo

```bash
git push -u origin fix/short-description
```

## 4) Open a pull request into `main`

Use GitHub PRs for review and history tracking.

Suggested PR checklist:
- What changed and why
- How you tested it
- Any caveats or follow-ups
- Link to related issues if relevant

## 5) Wait for CI

The repo already runs CI on pull requests:
- `Tests` workflow
- contributor checks where applicable

## 6) Merge back to `main`

Prefer a merge commit for feature branches so the branch history remains visible.

## Notes

- Keep PRs small and focused.
- If a change touches gateway, voice, tools, or auth paths, run the relevant targeted tests before opening the PR.
- This document is the private-repo companion to `CONTRIBUTING.md`.
