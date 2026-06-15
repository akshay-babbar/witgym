## 2026-06-15 - UI Browser Testing On Worktrees
- Problem: browser-based UI validation in this repo became fragile from a Codex git worktree even when the UI change itself was small.
- Root cause: worktree git metadata, missing runtime dependencies in the worktree, and browser blocking of `file://` previews created verification friction unrelated to the code.
- Keep doing: if browser testing gets sticky, switch to a normal branch checkout and serve previews over localhost.
- Avoid: spending hackathon time debugging worktree-specific UI testing failures or relying on `file://` preview URLs.
