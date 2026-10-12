#!/usr/bin/env python3
"""Hatchery Telegram bot (python3.9+, standard library only).

Runs from GitHub Actions every ~15 minutes (see .github/workflows/alerts.yml):
  * incubator alerts: turning reminders, daily summary, candling, lockdown, hatch day
  * reminders built by the portal: vaccinations, deliveries, follow-ups, pending payments
  * commands: /help /status /today /reminders /batches  (answered on each run)

Env: TG_TOKEN (GitHub secret). The chat id is found automatically: press Start in your bot and run the
workflow; the first private /start is paired and remembered. Optional: TG_CHAT_ID (fixed id),
TG_PAIR_CODE (then pair with /start <code>), TURN_HOURS, SUMMARY_HOUR, TZ, BATCHES_FILE.
Local helpers:  --find-chat   --test
"""
import json, os, re, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("TG_TOKEN", "").strip().strip("'\"")
CHAT = os.environ.get("TG_CHAT_ID", "").strip().strip("'\"")
BFILE = os.environ.get("BATCHES_FILE", os.path.join(HERE, "batches.json"))
SFILE = os.path.join(HERE, "alerts_sent.json")
TURN_HOURS = [int(x) for x in os.environ.get("TURN_HOURS", "7,11,15,19,22").split(",") if x.strip()]
SUMMARY_HOUR = int(os.environ.get("SUMMARY_HOUR", "7"))
TZ = ZoneInfo(os.environ.get("TZ", "Asia/Kolkata"))

# days, lockdown day, humidity normal, humidity lockdown, candling days
SP = {
    "chicken": (21, 18, (45, 55), (65, 75), (7, 14, 18)),
    "quail": (18, 15, (45, 50), (65, 70), (7, 14)),
    "duck": (28, 25, (55, 60), (70, 75), (7, 14, 25)),
    "muscovy": (35, 32, (55, 60), (70, 75), (7, 14, 21, 32)),
    "goose": (30, 27, (55, 60), (70, 75), (7, 14, 27)),
    "turkey": (28, 25, (50, 55), (65, 70), (7, 14, 25)),
    "guinea fowl": (28, 25, (50, 55), (65, 70), (7, 14, 25)),
    "peafowl": (28, 25, (50, 55), (65, 70), (7, 14, 25)),
    "pigeon": (18, 15, (50, 55), (60, 65), (7, 14)),
}
TEMP = {"still": "38.3-39.5 C (at egg top)", "forced": "37.2-37.8 C"}
TEMPR = {"still": (38.3, 39.5), "forced": (37.2, 37.8)}
HELP = ("Hatchery bot commands:\n/status - active batches, turns done today, last readings\n/today - turning and humidity check hours, reminders for today\n"
        "/reminders - next 7 days\n/batches - batch list with hatch dates\n/help - this message")


def tg(method, **params):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=25) as r:
        return json.load(r)


def send(text):
    for i in range(0, len(text), 3800):
        tg("sendMessage", chat_id=CHAT, text=text[i:i + 3800])


def find_chat():
    res = tg("getUpdates")
    seen = {}
    for u in res.get("result", []):
        c = (u.get("message") or u.get("channel_post") or {}).get("chat")
        if c:
            seen[c["id"]] = c.get("first_name") or c.get("title") or ""
    if not seen:
        print("No messages yet. Send /start to your bot, then run again.")
    for cid, name in seen.items():
        print(f"chat id: {cid}  ({name})")


def profile(b):
    sp = (b.get("species") or "").lower()
    if sp in SP:
        return SP[sp]
    n = int(b.get("custom_days") or 21)
    return (n, n - 3, (50, 55), (65, 70), (7, 14, n - 3))


def stamp(now):
    return f"\U0001F552 {now:%d %b %Y, %I:%M %p}"


def ago(now, ts):
    m = int((now - datetime.fromisoformat(ts).replace(tzinfo=TZ)).total_seconds() // 60)
    return f"{m} min ago" if m < 60 else f"{m // 60} h ago" if m < 1440 else f"{m // 1440} d ago"


def batch_lines(cfg, today, now=None):
    out = []
    n_turns = len(cfg.get("turn_hours") or TURN_HOURS)
    for b in cfg.get("batches", []):
        if b.get("done"):
            continue
        n, lock, h1, h2, _ = profile(b)
        day = (date.fromisoformat(b["set_date"]) - today).days * -1
        if day < 0:
            out.append(f"\U0001F95A {b['name']}: starts {b['set_date']}")
            continue
        hum = h2 if day >= lock else h1
        phase = "turning" if day < lock else "lockdown (no turning)"
        hatch = date.fromisoformat(b["set_date"]) + timedelta(days=n)
        line = (f"\U0001F95A {b['name']} ({b.get('species')}): day {day}/{n}, {n - day} days left, {phase}.\n"
                f"   Hatch {hatch:%d %b}. Humidity {hum[0]}-{hum[1]}%, temp {TEMP.get(cfg.get('air', 'still'), TEMP['still'])}.")
        extra = []
        if now is not None and "turns_today" in b and 1 <= day < lock:
            extra.append(f"Turns today: {b['turns_today']}/{n_turns}")
        for key, label, unit in (("last_t", "Temp", " C"), ("last_h", "Humidity", "%")):
            lr = b.get(key)
            if now is not None and lr and lr.get("ts"):
                extra.append(f"{label} {lr['v']}{unit} ({ago(now, lr['ts'])})")
        out.append(line + ("\n   " + " | ".join(extra) if extra else ""))
    return out


def due_reminders(cfg, today, horizon=0):
    """Reminders whose date has come (horizon=0) or falls within the next `horizon` days."""
    out = []
    for r in cfg.get("reminders", []):
        d = (today - date.fromisoformat(r["date"])).days
        if horizon == 0:
            every, until = int(r.get("every", 1)), int(r.get("until", 3))
            if d >= 0 and d <= until and d % every == 0:
                out.append(r["text"])
        elif -horizon <= d <= 0:
            out.append(f"{date.fromisoformat(r['date']):%d %b}: {r['text']}")
    return out


def handle_commands(cfg, sent, now):
    today = now.date()
    res = tg("getUpdates", offset=int(sent.get("offset", 0)), timeout=0)
    for u in res.get("result", []):
        sent["offset"] = u["update_id"] + 1
        m = u.get("message") or {}
        if str((m.get("chat") or {}).get("id")) != str(CHAT):
            continue  # ignore everyone except the owner
        cmd = (m.get("text") or "").strip().split()[0].split("@")[0].lower() if m.get("text") else ""
        if cmd in ("/start", "/help"):
            send(HELP)
        elif cmd == "/status":
            L = batch_lines(cfg, today, now)
            send("\n\n".join(L) + "\n\n" + stamp(now) if L else "No active batches.")
        elif cmd == "/batches":
            L = []
            for b in cfg.get("batches", []):
                if b.get("done"):
                    continue
                n = profile(b)[0]
                sd = date.fromisoformat(b["set_date"])
                L.append(f"\U0001F95A {b['name']} ({b.get('species')}): set {sd:%d %b}, day {(today - sd).days}/{n}, hatch {sd + timedelta(days=n):%d %b %Y}")
            send("\n".join(L) if L else "No active batches.")
        elif cmd == "/today":
            hours = cfg.get("turn_hours") or TURN_HOURS
            R = due_reminders(cfg, today)
            fmt = lambda hs: ", ".join(f"{h % 12 or 12}{'AM' if h < 12 else 'PM'}" for h in sorted(hs))
            hum_h = (cfg.get("alerts") or {}).get("hum_hours") or [8, 14, 20]
            send("\U0001F504 Turning hours: " + fmt(hours) + "\n\U0001F4A7 Humidity checks: " + fmt(hum_h) +
                 "\n\n" + ("\n".join(R) if R else "No reminders due today.") + "\n\n" + stamp(now))
        elif cmd == "/reminders":
            R = due_reminders(cfg, today, 7)
            send("\n".join(R) if R else "No reminders in the next 7 days.")
        elif cmd:
            send("Unknown command. Send /help")


def save(sent):
    with open(SFILE, "w") as f:
        json.dump(sent, f)


def pair(sent):
    """First private /start (with the pair code, if one is set) becomes the owner chat."""
    global CHAT
    code = os.environ.get("TG_PAIR_CODE", "").strip()
    res = tg("getUpdates", offset=int(sent.get("offset", 0)), timeout=0)
    for u in res.get("result", []):
        sent["offset"] = u["update_id"] + 1
        m = u.get("message") or {}
        c = m.get("chat") or {}
        parts = (m.get("text") or "").split()
        if c.get("type") != "private" or not parts or parts[0].split("@")[0].lower() != "/start":
            continue
        if code and (len(parts) < 2 or parts[1] != code):
            tg("sendMessage", chat_id=c["id"], text="Pairing code missing or wrong.")
            continue
        CHAT = str(c["id"])
        sent["chat_id"] = CHAT
        send("\u2705 Paired. I will send your hatchery alerts to this chat. Send /help for commands.")
        return True
    return False


def main():
    global CHAT
    if "--find-chat" in sys.argv:
        return find_chat()
    if not re.fullmatch(r"\d{6,}:[A-Za-z0-9_-]{30,}", TOKEN):
        sys.exit("ERROR: the TG_TOKEN secret is missing or is not a bot token. Repo > Settings > Secrets and variables > Actions: "
                 "set TG_TOKEN to the token from @BotFather (looks like 123456789:AAE..., no quotes, no spaces).")
    now = datetime.now(TZ)
    today = now.date()
    try:
        with open(BFILE) as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    try:
        with open(SFILE) as f:
            sent = json.load(f)
    except Exception:
        sent = {}
    cutoff = (today - timedelta(days=10)).isoformat()
    sent = {k: v for k, v in sent.items() if k in ("offset", "chat_id") or k[:10] >= cutoff}
    if not CHAT:
        CHAT = str(sent.get("chat_id", ""))
    if not CHAT and not pair(sent):
        save(sent)
        print("Not paired yet. Open your bot in Telegram, press Start, then run this workflow again.")
        return
    if "--test" in sys.argv:
        return send("Hatchery bot connected.\n" + stamp(now))

    al = cfg.get("alerts", {})
    hours = {int(h) for h in (cfg.get("turn_hours") or TURN_HOURS)}
    sum_hour = int(al.get("sum_hour") or SUMMARY_HOUR)
    hum_hours = {int(h) for h in (al.get("hum_hours") or [8, 14, 20])}
    msgs = []

    def once(key, text):
        k = f"{today.isoformat()}|{key}"
        if k not in sent:
            sent[k] = 1
            msgs.append(text)

    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        msgs.append("\u2705 Hatchery bot connected. Send /help to see commands.")

    for b in cfg.get("batches", []):
        if b.get("done"):
            continue
        n, lock, h1, h2, candle = profile(b)
        set_d = date.fromisoformat(b["set_date"])
        day = (today - set_d).days
        bid = f'{b["name"]}|{b["set_date"]}'
        name = b["name"]
        if day < 0:
            continue
        hum = h2 if day >= lock else h1
        hatch = set_d + timedelta(days=n)
        if al.get("turns", True) and 1 <= day < lock and now.hour in hours:
            once(f"turn|{now.hour}|{bid}", f"\U0001F504 {name}: turn the eggs now (day {day}/{n}). {len(hours)} turns today.")
        if al.get("hum", True) and 0 <= day <= n and now.hour in hum_hours:
            once(f"hum|{now.hour}|{bid}", f"\U0001F4A7 {name}: check humidity and temperature now.\n   Target humidity {hum[0]}-{hum[1]}%, temperature {TEMP.get(cfg.get('air', 'still'), TEMP['still'])}. Log it in the portal.")
        passed = [h for h in sorted(hours) if h < now.hour]
        if al.get("missed", True) and 1 <= day < lock and passed and (now.hour - 1) in hours and len(passed) > int(b.get("turns_today") or 0):
            once(f"miss|{now.hour}|{bid}", f"\u26A0\uFE0F {name}: turn missed? {int(b.get('turns_today') or 0)} of {len(passed)} turns logged so far today. Turn the eggs now and tick it in the portal.")
        trange = TEMPR.get(cfg.get("air", "still"), TEMPR["still"])
        for key, label, rng, unit in (("last_t", "temperature", trange, " C"), ("last_h", "humidity", hum, "%")):
            lr = b.get(key)
            if al.get("range", True) and lr and lr.get("ts"):
                age = now - datetime.fromisoformat(lr["ts"]).replace(tzinfo=TZ)
                if age < timedelta(hours=12) and not (rng[0] <= lr["v"] <= rng[1]):
                    once(f"range|{key}|{lr['ts']}|{bid}", f"\U0001F321 {name}: last {label} {lr['v']}{unit} is outside {rng[0]}-{rng[1]}{unit}. Fix it and log a new reading.")
        if al.get("stale", True) and 0 <= day <= n and 9 <= now.hour <= 21:
            stamps = [b[k]["ts"] for k in ("last_t", "last_h") if b.get(k) and b[k].get("ts")]
            last = max(stamps) if stamps else None
            if last is None or now - datetime.fromisoformat(last).replace(tzinfo=TZ) > timedelta(hours=14):
                once(f"stale|{now.hour // 6}|{bid}", f"\U0001F4DD {name}: no temperature or humidity reading logged in the last 14 hours.")
        if now.hour >= sum_hour:
            phase = "turning" if day < lock else "lockdown (no turning)"
            if al.get("summary", True) and day <= n:
                once(f"sum|{bid}", f"\U0001F95A {name} ({b.get('species')}): day {day}/{n}, {n - day} days left.\n"
                     f"Hatch date {hatch:%d %b %Y}. Phase: {phase}.\n"
                     f"Temp {TEMP.get(cfg.get('air', 'still'), TEMP['still'])}, humidity {hum[0]}-{hum[1]}%.")
            if day in candle and day != lock:
                once(f"candle|{bid}", f"\U0001F526 {name}: candling day (day {day}). Remove clear and blood-ring eggs.")
            if day == lock - 1:
                once(f"prelock|{bid}", f"\u26A0\uFE0F {name}: lockdown tomorrow. Do the last turn today.")
            if day == lock:
                once(f"lock|{bid}", f"\U0001F512 {name}: LOCKDOWN today. Stop turning, raise humidity to {h2[0]}-{h2[1]}%, do not open the incubator.")
            if day == n:
                once(f"hatch|{bid}", f"\U0001F423 {name}: hatch day! Keep the incubator closed.")
            if day > n:
                once(f"over|{bid}", f"\u2757 {name}: {day - n} day(s) past hatch date. Check eggs; archive the batch if done.")

    if now.hour >= sum_hour:
        for r in cfg.get("reminders", []):
            d = (today - date.fromisoformat(r["date"])).days
            if 0 <= d <= int(r.get("until", 3)) and d % int(r.get("every", 1)) == 0:
                once(f"rem|{r['key']}", r["text"])

    if msgs:
        send("\n\n".join(msgs) + "\n\n" + stamp(now))
    try:
        handle_commands(cfg, sent, now)
    except urllib.error.HTTPError as e:
        if e.code in (401, 404):
            raise  # bad token: fail loudly so the problem is visible in the Actions log
        print("command handling failed:", e)
    except Exception as e:  # never lose the state file because of a command error
        print("command handling failed:", e)
    save(sent)


def run():
    try:
        main()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:200]
        except Exception:
            detail = ""
        why = {
            401: "Telegram says the bot token is invalid or revoked. Put the CURRENT token from @BotFather into the TG_TOKEN secret.",
            404: "Telegram says not found. TG_TOKEN is wrong (typo, extra characters, quotes, or a revoked token).",
            400: "Telegram rejected the request. If it says 'chat not found', TG_CHAT_ID is wrong or you have not pressed Start in the bot. Delete TG_CHAT_ID to let the bot pair by itself.",
            403: "The bot was blocked or cannot message this chat. Open the bot in Telegram and press Start.",
        }.get(e.code, "Telegram returned an error.")
        sys.exit(f"ERROR (HTTP {e.code}): {why} {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: could not reach Telegram: {e.reason}")


if __name__ == "__main__":
    run()
