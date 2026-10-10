#!/usr/bin/env python3
"""Incubator Telegram alerts (python3.9+, no pip packages).

Env vars:
  TG_TOKEN       bot token (keep it ONLY here, never in the web page)
  TG_CHAT_ID     your chat id (get it with --find-chat)
Optional:
  BATCHES_FILE   default: batches.json next to this script
  TURN_HOURS     default "7,11,15,19,22"  (hours when turn reminders go out)
  SUMMARY_HOUR   default 7                (daily summary + milestone alerts)
  TZ             default Asia/Kolkata

Usage:
  python3 incubator_alerts.py --find-chat   # after sending /start to your bot
  python3 incubator_alerts.py --test        # sends a test message
  python3 incubator_alerts.py               # normal run (cron every 15 min)
"""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("TG_TOKEN", "")
CHAT = os.environ.get("TG_CHAT_ID", "")
BFILE = os.environ.get("BATCHES_FILE", os.path.join(HERE, "batches.json"))
SFILE = os.path.join(HERE, "alerts_sent.json")
TURN_HOURS = {int(x) for x in os.environ.get("TURN_HOURS", "7,11,15,19,22").split(",") if x.strip()}
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


def tg(method, **params):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
        return json.load(r)


def send(text):
    tg("sendMessage", chat_id=CHAT, text=text)


def find_chat():
    res = tg("getUpdates")
    seen = {}
    for u in res.get("result", []):
        m = u.get("message") or u.get("channel_post") or {}
        c = m.get("chat")
        if c:
            seen[c["id"]] = c.get("first_name") or c.get("title") or ""
    if not seen:
        print("No messages yet. Send /start to your bot in Telegram, then run again.")
    for cid, name in seen.items():
        print(f"chat id: {cid}  ({name})")


def profile(b):
    sp = (b.get("species") or "").lower()
    if sp in SP:
        return SP[sp]
    n = int(b.get("custom_days") or 21)
    return (n, n - 3, (50, 55), (65, 70), (7, 14, n - 3))


def main():
    if "--find-chat" in sys.argv:
        return find_chat()
    if not TOKEN or not CHAT:
        sys.exit("Set TG_TOKEN and TG_CHAT_ID first.")
    if "--test" in sys.argv:
        return send(f"Incubator alerts connected.\n🕒 {datetime.now(TZ):%d %b %Y, %I:%M %p}")

    now = datetime.now(TZ)
    today = now.date()
    with open(BFILE) as f:
        cfg = json.load(f)
    try:
        with open(SFILE) as f:
            sent = json.load(f)
    except Exception:
        sent = {}
    cutoff = (today - timedelta(days=10)).isoformat()
    sent = {k: 1 for k in sent if k[:10] >= cutoff}

    air = cfg.get("air", "still")
    hours = {int(h) for h in (cfg.get("turn_hours") or TURN_HOURS)}
    turns = len(hours)
    msgs = []

    def once(key, text):
        k = f"{today.isoformat()}|{key}"
        if k not in sent:
            sent[k] = 1
            msgs.append(text)

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

        if 1 <= day < lock and now.hour in hours:
            once(f"turn|{now.hour}|{bid}", f"🔄 {name}: turn the eggs now (day {day}/{n}). Target {turns} turns today.")

        if now.hour >= SUMMARY_HOUR:
            phase = "turning" if day < lock else "lockdown (no turning)"
            if day <= n:
                once(f"sum|{bid}",
                     f"🥚 {name} ({b.get('species')}): day {day}/{n}, {n - day} days left.\n"
                     f"Hatch date {hatch:%d %b %Y}. Phase: {phase}.\n"
                     f"Temp {TEMP.get(air, TEMP['still'])}, humidity {hum[0]}-{hum[1]}%.")
            if day in candle and day != lock:
                once(f"candle|{bid}", f"🔦 {name}: candling day (day {day}). Remove clear and blood-ring eggs.")
            if day == lock - 1:
                once(f"prelock|{bid}", f"⚠️ {name}: lockdown tomorrow. Do the last turn today.")
            if day == lock:
                once(f"lock|{bid}", f"🔒 {name}: LOCKDOWN today. Stop turning, raise humidity to {h2[0]}-{h2[1]}%, do not open the incubator.")
            if day == n:
                once(f"hatch|{bid}", f"🐣 {name}: hatch day! Keep the incubator closed.")
            if day > n:
                once(f"over|{bid}", f"❗ {name}: {day - n} day(s) past hatch date. Check eggs; archive the batch if done.")

    if msgs:
        send("\n\n".join(msgs) + f"\n\n🕒 {now:%d %b %Y, %I:%M %p}")
    with open(SFILE, "w") as f:
        json.dump(sent, f)


if __name__ == "__main__":
    main()
