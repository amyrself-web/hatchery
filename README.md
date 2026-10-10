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
3. Browser: `https://api.telegram.org/bot<TOKEN>/getUpdates`, copy `"chat":{"id":...}`.
4. Repo > Settings > Secrets and variables > Actions: add `TG_TOKEN` and `TG_CHAT_ID`.
5. Actions > Incubator alerts > Run workflow. You should receive "Hatchery bot connected".
6. Portal > Settings > GitHub sync (repo + fine-grained token, Contents read and write).
7. Commands: /help /status /today /reminders /batches. Answered on each run (about every 15 min; GitHub may delay).

Privacy: `batches.json` is public if the repo is public. Customer names are left out of alerts unless you switch that on in the Telegram tab.

## Login
Screen lock stored on the device (password hash in the browser), not a server login.
