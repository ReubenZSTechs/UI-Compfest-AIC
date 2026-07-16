# Contributing

Thanks for contributing! This document covers the basics for working on this repo as a team.

## Branching model
- `main` — production-ready code only. Protected, no direct pushes.
- `develop` — integration branch. Protected, PRs required.
- Feature branches: `feat/short-description`
- Bug fix branches: `fix/short-description`
- Chore/infra branches: `chore/short-description`

## Workflow
1. Pick up (or create) an Issue and assign yourself; move it to "In Progress" on the Project board.
2. Branch off `develop`: `git checkout -b feat/my-feature develop`
3. Commit using clear messages (see convention below).
4. Open a Pull Request into `develop`. Fill out the PR template fully.
5. Link the PR to its issue with `Closes #<issue-number>`.
6. Request review from the relevant CODEOWNER (usually automatic).
7. Address review comments, get at least 1 approval, and ensure CI passes.
8. Squash-merge once approved. Delete the branch after merge.

## Commit message convention
Use [Conventional Commits](https://www.conventionalcommits.org/):
```
feat: add user authentication endpoint
fix: correct GPU memory leak in model loader
docs: update setup instructions in wiki
chore: bump dependency versions
```

## Code style / quality
- Run linters locally before pushing (see CI workflow for exact tools/commands used).
- Add or update tests for any behavior change.
- Keep PRs focused and reasonably small — easier to review, faster to merge.

## Getting help
- General questions: use GitHub Discussions (if enabled) or the team chat.
- Bugs/feature ideas: open an Issue using the appropriate template.
