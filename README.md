# Hatchery Control

Manual incubator tracker (web portal) + Telegram alerts, hosted free on GitHub.

- `index.html` – the portal (GitHub Pages)
- `batches.json` – your batches (the portal updates it via GitHub sync)
- `incubator_alerts.py` + `.github/workflows/alerts.yml` – sends Telegram alerts every ~15 min

## Setup
1. Create a GitHub repo (public, needed for free Pages) and upload all files, including the `.github` folder.
2. Settings > Pages > Deploy from branch `main` / root. Portal URL: `https://<user>.github.io/<repo>/`
3. Create a NEW bot token with @BotFather (/revoke the old one). Message your bot `/start`, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy `"chat":{"id":...}`.
4. Settings > Secrets and variables > Actions > New secret: `TG_TOKEN` and `TG_CHAT_ID`.
5. Actions tab > "Incubator alerts" > Run workflow. You should get alerts once a batch exists.
6. In the portal, Excel tab > GitHub sync: repo `<user>/<repo>` + a fine-grained token
   (only this repo, Contents: read & write). Batches then sync automatically.

Notes: GitHub cron can run a few minutes late. Scheduled workflows pause after 60 days without repo activity.

## Login
The portal has a login screen (name + password). It is a screen lock stored on the device (password hash in the browser),
not a server login. GitHub Pages has no backend, so real multi-user login needs a service such as Firebase or Supabase.
"Forgot password?" removes the login on that device; your batches and logs stay.
