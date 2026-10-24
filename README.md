# Hatchery Control: poultry farm manager

Free hosting on GitHub: portal on GitHub Pages, Telegram bot on GitHub Actions.

## Modules
- Dashboard: farm KPIs (birds, eggs, revenue, expenses, profit, dues), egg chart, alerts, incubator batches
- Incubator: batches, day-by-day, charts, candling, hatch results, log, egg guide
- Flocks and daily records (eggs, broken, deaths, feed)
- Health: vaccination and medicine log, standard vaccine schedule, due dates
- Customers (CRM): contacts, follow-ups, order history, balance, call and WhatsApp links
- Sales: items, rate, payments, delivery status, receive payment
- Expenses by category
- Telegram: guided bot setup and alert preferences
- Settings: incubator type, turning hours, Excel export/import, GitHub sync

## Files
- `index.html` portal, `batches.json` data for the bot (written by the portal)
- `incubator_alerts.py` bot, `.github/workflows/alerts.yml` scheduler

## Telegram bot, full process
1. @BotFather: `/newbot`, copy the token. Never put the token in the portal, chats or repo files. Leaked? `/revoke`.
2. Open your bot and press Start.
3. Repo > Settings > Secrets and variables > Actions: add `TG_TOKEN`. A chat id is not needed: the bot pairs with the first private /start. (Optional `TG_PAIR_CODE`: then pair with `/start <code>`. If you set `TG_CHAT_ID` and it is wrong, the bot falls back to pairing.)
4. If a run fails, open it in the Actions tab: the reason is shown at the top as an annotation.
5. Actions > Incubator alerts > Run workflow. You should receive "Hatchery bot connected".
6. Portal > Settings > GitHub sync (repo + fine-grained token, Contents read and write).
7. Commands: /help /status /today /reminders /batches. Each run stays online for about 52 minutes and answers within seconds; the next scheduled run takes over. Between runs (GitHub sometimes starts them late) a command waits until the next run.
   This keeps one Actions job running most of the time, which is free for a public repo. If the repo is made private it would use up the free minutes, so lower `LISTEN_MINUTES` in the workflow.

## Privacy and backup
- `batches.json` is public if the repo is public. Customer names and task titles are left out of alerts unless you switch that on in the Alerts tab.
- GitHub and Telegram tokens are stored in the browser encrypted with your login password (AES-256-GCM, PBKDF2). Forgot password: the data stays, the tokens must be entered again.
- Settings > Encrypted backup: pushes `backup.enc.json` (all your data, encrypted with a backup passphrase) to the repo, automatically every 6 hours while sync runs. Restore it on any device with the passphrase. Lose the passphrase and the backup cannot be opened, so write it down.

## Login
Screen lock stored on the device (password hash in the browser), not a server login. The password also unlocks the saved tokens.
