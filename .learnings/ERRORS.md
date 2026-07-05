# ERRORS.md

## [ERR-20260705-001] git_commit_identity

**Logged**: 2026-07-05T04:20:00Z
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
Initial workspace commit failed because local git author identity was not configured.

### Error
```text
Author identity unknown
fatal: unable to auto-detect email address
```

### Context
- Command attempted: `git commit -m "first commit"`
- Workspace: `/home/node/.openclaw/workspace`
- Cause: repository had no local `user.name` or `user.email`.

### Suggested Fix
Set repository-local git identity before committing:

```bash
git config user.name "OpenClaw Agent"
git config user.email "openclaw-agent@users.noreply.github.com"
```

### Metadata
- Reproducible: yes
- Related Files: `.git/config`

### Resolution
- **Resolved**: 2026-07-05T04:20:00Z
- **Notes**: Added repository-local git identity and retried the commit.

---

## [ERR-20260705-002] git_push_https_auth

**Logged**: 2026-07-05T04:28:00Z
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
CLI `git push origin main` failed because HTTPS GitHub credentials were not available in the runtime.

### Error
```text
fatal: could not read Username for 'https://github.com': No such device or address
```

### Context
- Command attempted: `git push origin main`
- Remote: `https://github.com/7cmdehdrb/openclaw_skills_ver2.git`
- GitHub connector had push/admin permission, but local git credential storage was empty.

### Suggested Fix
For CLI push, configure `gh auth login`, SSH keys, or a credential helper/PAT. If CLI auth is unavailable, use the GitHub connector/API to create commits and update `main`.

### Metadata
- Reproducible: yes
- Related Files: `.git/config`, `TOOLS.md`

### Resolution
- **Resolved**: 2026-07-05T04:28:00Z
- **Notes**: Used the GitHub connector to create the remote commits, then fetched `origin/main` locally and aligned the branch.

---
