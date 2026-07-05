# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## GitHub Workspace Sync

- Active repo: `https://github.com/7cmdehdrb/openclaw_skills_ver2.git`
- Branch: `main`
- Local git remote is configured as `origin`, but HTTPS CLI push currently has no stored credentials in this runtime.
- When CLI `git push` cannot authenticate, use the GitHub connector/API to create a tree, create a commit, and update `main`; then `git fetch origin main` and align local `main` to `origin/main`.
- For normal CLI pushes, first configure GitHub auth with `gh auth login`, SSH keys, or a credential helper/PAT approved by 소유.

## Related

- [Agent workspace](/concepts/agent-workspace)
