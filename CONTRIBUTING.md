# Contributing & Git Workflow

This project doubles as a git learning project. The workflow is **GitHub Flow**: `main` is always working, every change
happens on its own branch, and lands in `main` through a Pull Request (PR) after CI passes.

```
main ──●──────────────●───────────────●──────►   (always green, protected)
        \            / \             /
         ●──●──●────●   ●──●──●─────●             feat/epub-parser   → PR → merge
          \
           ●──●──●──●──●──────────────►           feat/quiz-engine   (in parallel)
```

## 1. Branch naming

| Prefix | Use for | Example |
|--------|---------|---------|
| `feat/` | new feature | `feat/epub-parser` |
| `fix/` | bug fix | `fix/quiz-duplicate-options` |
| `chore/` | tooling, CI, deps | `chore/dev-workflow` |
| `docs/` | docs only | `docs/architecture` |
| `refactor/` | restructuring, no behaviour change | `refactor/scoring-module` |
| `test/` | tests only | `test/distractor-edge-cases` |

Lowercase, hyphen-separated, short.

## 2. Day-to-day loop

```bash
git switch main                 # go to main
git pull                        # get latest main from GitHub
git switch -c feat/epub-parser  # create + switch to a new branch

# ...edit code...
git status                      # what changed?
git diff                        # see the exact changes
git add -p                      # stage changes hunk by hunk (review as you go)
git commit -m "feat(extraction): parse EPUB chapters from spine"

git push -u origin feat/epub-parser   # first push; later just `git push`
gh pr create --fill                   # open a Pull Request
gh pr checks                          # watch CI
gh pr merge --squash --delete-branch  # merge when green
```

**Keeping a branch up to date with main** (when main moved on while you worked):

```bash
git fetch origin
git rebase origin/main          # replay your commits on top of the latest main
# on conflicts: fix files → git add <file> → git rebase --continue   (or git rebase --abort)
git push --force-with-lease     # safe force-push of your rewritten branch only
```

## 3. Working on several features in parallel

Option A, **switching branches** (simple): commit or stash first, then switch.

```bash
git stash            # park uncommitted work
git switch feat/quiz-engine
git switch -         # jump back to the previous branch
git stash pop        # restore parked work
```

Option B, **worktrees** (recommended for real parallel work): each branch gets its own folder, so nothing needs
stashing.

```bash
git worktree add ../vocab_sensei-quiz -b feat/quiz-engine
git worktree list
git worktree remove ../vocab_sensei-quiz    # after the branch is merged
```

## 4. Commit messages: Conventional Commits

```
<type>(<scope>): <short summary in imperative mood>

<optional body: why, not what>
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `perf`.
Scopes: `extraction`, `dictionary`, `quiz`, `scoring`, `api`, `db`, `frontend`, `ci`.

Small, focused commits are easier to review and to revert.

## 5. Pull Requests
- One feature per PR, ideally < 400 changed lines.
- Fill in the PR template (what, why, how tested).
- CI must be green. `main` is protected: no direct pushes.
- **Squash merge**: the whole branch becomes one clean commit on `main`.

## 6. Local quality checks

All tools are free & open source.

```bash
pipx install pre-commit   # or: uv tool install pre-commit / brew install pre-commit
pre-commit install        # runs checks automatically on every `git commit`
pre-commit run --all-files
```

CI runs the same checks, so if it passes locally it should pass on GitHub.

## 7. Handy git commands

| Command | What it does |
|---------|--------------|
| `git log --oneline --graph --all` | visual branch history |
| `git branch -a` | list local + remote branches |
| `git restore <file>` | discard uncommitted changes in a file |
| `git restore --staged <file>` | unstage a file |
| `git commit --amend` | fix the last commit (before pushing) |
| `git revert <sha>` | undo a commit safely by adding a new one |
| `git reflog` | "undo history": recover almost anything |
| `git tag -a v0.1.0 -m "MVP"` | mark a release |
