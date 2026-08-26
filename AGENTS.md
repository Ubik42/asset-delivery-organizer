# Development rules

- Start by reading `config/goal-state.json`, its `lastCheckpoint`, and `docs/CODEX_GOAL.md`.
- Run `scripts/goal.ps1 -Action Doctor` before implementation and `scripts/validate.ps1 -Tier quick` before advancing state.
- `config/goal-state.json` is the progress source of truth. Validation command strings are documentation only and must never be executed dynamically.
- Keep the core runnable without a DCC installation.
- File mutations require a dry-run plan, collision checks, and post-run verification.
- Put host-specific code behind adapters; do not duplicate the core UI per DCC.
- Treat `docs/REFERENCE_BRIEF.md` as requirements inspiration, not implemented evidence.
- Auditing remains strictly read-only. Organization may mutate only an explicitly approved plan after full preflight, must never overwrite a target, must roll back partial work, write its receipt outside the delivery root, and run a post-audit.
- Never mutate `demo/scenarios`; copy fixtures into `work/` or another generated workspace before organization tests or demonstrations.
