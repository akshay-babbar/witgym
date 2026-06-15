# UI browser testing in this repo should move from worktree to normal branch

## Problem
- UI closed-loop testing with the in-app browser became unreliable while working from a Codex git worktree.
- The agent needed browser automation on localhost or browser-visible artifacts, but branch/worktree metadata and local runtime setup kept creating friction.

## Why It Persisted
- The code changes themselves were frontend-only and small, but verification depended on multiple layers: git worktree state, local runtime availability, and browser URL-policy constraints.
- Detached HEAD / worktree-specific git metadata created extra branch-management friction right before UI verification.
- The browser surface blocked direct file:// navigation, which made static preview verification harder unless served over localhost.

## Paths Tried
- Tried to continue from detached HEAD in the worktree, then corrected to a feature branch off origin/main.
- Tried to launch the full app with uv; hit cache permission issues and then a uv runtime panic unrelated to product code.
- Tried to open a static preview via file:// in the browser; browser security policy blocked that path.
- Switched to the safer localhost-preview approach.

## Root Cause
- In this repo, UI verification from a Codex worktree can fail for operational reasons that are orthogonal to the UI change itself: shared git worktree metadata permissions, missing local dependency installation in the worktree, and browser policy restrictions on file:// URLs.

## Pareto-Optimal Solution
- If UI testing starts fighting the agent while on a worktree, switch to a normal branch checkout for browser-based validation rather than burning time debugging worktree-specific friction.
- For static UI proof, prefer serving a preview over localhost instead of using file://, because the browser surface allows localhost but may block direct local-file navigation.

## Evidence
- `git checkout -b ...` from the worktree required elevated access to shared worktree git metadata outside the sandbox.
- `uv run python app.py` failed first on cache permissions, then with a uv/system-configuration panic.
- `python3 app.py` failed because the worktree runtime lacked installed dependencies like `python-dotenv`.
- Browser automation rejected `file:///private/tmp/...` with an explicit URL-policy block.
- `python3 -m http.server ...` on localhost succeeded once started with elevated permission.

## Future-Agent Rules
- If you are on a Codex worktree and UI testing starts failing for operational reasons, switch to a normal branch before spending more time on the worktree setup.
- For browser automation in this repo, prefer localhost-served previews over file:// artifacts.
- Distinguish environment/runtime failures from product regressions; do not misdiagnose launcher or policy problems as UI code bugs.

## Follow-Ups
- A normal-branch verification path is preferred for future high-pressure UI iterations.
- If full app runtime is required, ensure the branch environment has the expected dependencies installed before starting the browser loop.
