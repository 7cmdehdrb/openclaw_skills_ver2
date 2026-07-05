---
name: custom-env-app-runner
description: Run a user-provided Python app that requires a colocated .env file (.env, app.py, requirements.txt). Use when asked to install dependencies and execute this app.py with dotenv-loaded USER_ID/USER_PW.
---

# custom-env-app-runner

1. Keep `.env` in the same directory as `app.py`.
2. Use local virtual environment `.venv` in this skill directory.
3. Install dependencies with:
   - `.venv/bin/pip install -r requirements.txt`
4. Run app only when user explicitly requests:
   - `cd <skill_dir> && .venv/bin/python app.py`
5. Never print secret values from `.env`.
