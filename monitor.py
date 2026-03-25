#!/usr/bin/env python3
"""
MikroTik Monitor — GitHub Actions
Direct TCP connect se ISP check karta hai
"""

import socket
import json
import os
import time
import smtplib
import urllib.request
import urllib.error
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Configuration ─────────────────────────────────────────────
ROUTERS = [
    {
        "id": 1,
        "name": "Mikrotik #1 - CFI",
        "hosts": [
            {"ip": "115.42.66.83",    "port": 8081, "label": "Spotcomm"},
            {"ip": "125.209.101.214", "port": 8081, "label": "Multinet"},
        ]
    },
    {
        "id": 2,
        "name": "Mikrotik #2 - PECHS",
        "hosts": [
            {"ip": "113.203.193.201", "port": 8081, "label": "Optome"},
            {"ip": "103.245.193.137", "port": 8081, "label": "Storm Fiber"},
        ]
    }
]

DASHBOARD_URL = "https://cjinternet.free.nf/"
COOLDOWN_MIN  = 30

# ── TCP Check — direct socket, no HTTP proxy ──────────────────
def check_host(ip, port, timeout=5):
    start = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        ms = int((time.time() - start) * 1000)
        sock.close()
        if result == 0:
            return {"online": True, "ms": ms, "error": ""}
        else:
            return {"online": False, "ms": ms, "error": f"Port closed (code {result})"}
    except socket.timeout:
        ms = int((time.time() - start) * 1000)
        return {"online": False, "ms": ms, "error": "Timeout (5s)"}
    except Exception as e:
        ms = int((time.time() - start) * 1000)
        return {"online": False, "ms": ms, "error": str(e)}

# ── Send Email via Gmail SMTP ────────────────────────────────
def send_email(subject, html, text):
    gmail_user = os.environ.get("GMAIL_USER", "moba@cloudjunction.cloud")
    gmail_pass = os.environ.get("GMAIL_PASS", "sqru cqtu lbqm kkkd")
    to_addr    = os.environ.get("ALERT_TO",   "it-alerts@cloudjunction.cloud")

    if not gmail_user or not gmail_pass:
        print("  [SKIP] No GMAIL_USER or GMAIL_PASS set")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = gmail_user
        msg["To"]      = to_addr

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, to_addr, msg.as_string())

        print(f"  [EMAIL] Sent OK via Gmail → {to_addr}")
        return True
    except Exception as e:
        print(f"  [EMAIL] Failed: {e}")
        return False

# ── Build Email ───────────────────────────────────────────────
def build_email(etype, name, down_hosts, up_hosts, ts):
    is_down     = etype == "down"
    header_bg   = "#991b1b" if is_down else "#14532d"
    accent_col  = "#ef4444" if is_down else "#22c55e"
    status_txt  = "OFFLINE"  if is_down else "RESTORED"
    emoji       = "🔴" if is_down else "🟢"

    down_rows = ""
    for h in down_hosts:
        down_rows += (
            '<tr style="border-bottom:1px solid #fee2e2">'
            f'<td style="padding:10px 12px;width:12px"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#ef4444"></span></td>'
            f'<td style="padding:10px 12px;font-weight:600;font-size:13px;color:#1e293b">{h["label"]}</td>'
            f'<td style="padding:10px 12px;font-family:monospace;font-size:12px;color:#64748b">{h["ip"]}</td>'
            f'<td style="padding:10px 12px;font-size:12px;color:#ef4444">{h.get("error","Unreachable")}</td>'
            '</tr>'
        )

    up_rows = ""
    for h in up_hosts:
        up_rows += (
            '<tr style="border-bottom:1px solid #dcfce7">'
            f'<td style="padding:10px 12px;width:12px"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e"></span></td>'
            f'<td style="padding:10px 12px;font-weight:600;font-size:13px;color:#1e293b">{h["label"]}</td>'
            f'<td style="padding:10px 12px;font-family:monospace;font-size:12px;color:#64748b">{h["ip"]}</td>'
            f'<td style="padding:10px 12px;font-size:12px;color:#16a34a">{h["ms"]}ms</td>'
            '</tr>'
        )

    down_section = (
        '<div style="margin-bottom:20px">'
        '<p style="margin:0 0 8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#ef4444">Down Connections</p>'
        f'<table style="width:100%;border-collapse:collapse;background:#fef2f2;border-radius:8px;overflow:hidden">{down_rows}</table>'
        '</div>'
    ) if down_rows else ""

    up_section = (
        '<div style="margin-bottom:20px">'
        '<p style="margin:0 0 8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#16a34a">Active Connections</p>'
        f'<table style="width:100%;border-collapse:collapse;background:#f0fdf4;border-radius:8px;overflow:hidden">{up_rows}</table>'
        '</div>'
    ) if up_rows else ""

    action_box = (
        '<div style="margin-bottom:20px;padding:16px;background:#fffbeb;border-left:4px solid #f59e0b;border-radius:0 8px 8px 0">'
        '<p style="margin:0 0 8px;font-weight:700;font-size:13px;color:#b45309">Action Required</p>'
        '<ul style="margin:0;padding-left:20px;color:#92400e;font-size:13px;line-height:2">'
        '<li>Check router power supply</li>'
        '<li>Check physical cable connections</li>'
        '<li>Contact ISP if WAN link is down</li>'
        '<li>Try rebooting the router</li>'
        '</ul></div>'
    ) if is_down else (
        '<div style="margin-bottom:20px;padding:16px;background:#f0fdf4;border-left:4px solid #22c55e;border-radius:0 8px 8px 0">'
        '<p style="margin:0;font-weight:700;font-size:13px;color:#15803d">Connection restored successfully.</p>'
        '<p style="margin:6px 0 0;font-size:13px;color:#166534">Monitoring continues every 5 minutes.</p>'
        '</div>'
    )

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Segoe UI,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:30px 16px">
<tr><td align="center"><table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
<tr><td style="text-align:center;padding-bottom:14px">
<span style="font-size:12px;font-weight:700;color:#64748b;letter-spacing:1.5px;text-transform:uppercase">Cloud Junction &nbsp;&#8226;&nbsp; Network Monitor</span>
</td></tr>
<tr><td style="background:white;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.07)">
<div style="height:4px;background:linear-gradient(90deg,{accent_col},{'#f97316' if is_down else '#3b82f6'})"></div>
<div style="background:{header_bg};padding:28px 32px">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td>
<div style="display:inline-block;background:rgba(255,255,255,.15);border-radius:20px;padding:4px 14px;font-size:11px;font-weight:700;color:white;letter-spacing:1px;margin-bottom:10px">{emoji} &nbsp;{status_txt}</div>
<div style="font-size:22px;font-weight:800;color:white;line-height:1.2">{'Router Connection Lost' if is_down else 'Router Connection Restored'}</div>
<div style="font-size:14px;color:rgba(255,255,255,.75);margin-top:4px">{name}</div>
</td><td align="right" valign="top">
<div style="background:rgba(255,255,255,.1);border-radius:10px;padding:10px 14px;text-align:right">
<div style="font-size:10px;color:rgba(255,255,255,.6);text-transform:uppercase;letter-spacing:.5px">Detected At</div>
<div style="font-size:13px;font-weight:600;color:white;margin-top:3px;white-space:nowrap">{ts}</div>
</div></td></tr></table></div>
<div style="padding:28px 32px">
{down_section}{up_section}{action_box}
<div style="text-align:center;margin-top:8px">
<a href="{DASHBOARD_URL}" style="display:inline-block;background:linear-gradient(135deg,#3b82f6,#2563eb);color:white;text-decoration:none;padding:13px 32px;border-radius:10px;font-weight:700;font-size:14px;box-shadow:0 4px 12px rgba(59,130,246,.4)">Open Dashboard</a>
</div></div>
<div style="padding:16px 32px;background:#f8fafc;border-top:1px solid #f1f5f9;text-align:center">
<p style="margin:0;font-size:11px;color:#94a3b8">Auto-generated by <b>Cloud Junction Monitor</b> &nbsp;&#8226;&nbsp; Checks every 5 minutes<br>
<a href="{DASHBOARD_URL}" style="color:#3b82f6;text-decoration:none">{DASHBOARD_URL}</a></p>
</div>
</td></tr></table></td></tr></table>
</body></html>"""

    sep = "=" * 40
    down_txt = "\n".join([f"  DOWN: {h['label']} ({h['ip']}) - {h.get('error','Unreachable')}" for h in down_hosts])
    up_txt   = "\n".join([f"  UP:   {h['label']} ({h['ip']}) - {h['ms']}ms" for h in up_hosts])
    text = (
        f"{'ROUTER DOWN' if is_down else 'ROUTER RESTORED'}\n{sep}\n"
        f"Router : {name}\nStatus : {status_txt}\nTime   : {ts}\n\n"
        + (f"DOWN:\n{down_txt}\n\n" if down_txt else "")
        + (f"UP:\n{up_txt}\n\n"     if up_txt   else "")
        + ("Action: Check power, cables, ISP.\n\n" if is_down else "All connections restored.\n\n")
        + f"Dashboard: {DASHBOARD_URL}\n{sep}\nCloud Junction Network Monitor"
    )
    return html, text

# ── Push to GitHub ────────────────────────────────────────────
def push_github(data):
    import base64
    token = os.environ.get("GITHUB_TOKEN", "")
    user  = os.environ.get("GITHUB_USER",  "moba589")
    repo  = os.environ.get("GITHUB_REPO",  "mikrotik-monitor")

    if not token:
        print("  [SKIP] No GITHUB_TOKEN")
        return False

    api_url = f"https://api.github.com/repos/{user}/{repo}/contents/alert_log.json"
    headers = {
        "Authorization": f"token {token}",
        "Content-Type":  "application/json",
        "User-Agent":    "MikroTik-Monitor-GA",
    }

    # Get SHA
    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            sha = json.loads(resp.read())["sha"]
    except:
        pass

    content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
    payload = json.dumps({
        "message": f"Monitor {datetime.utcnow().strftime('%H:%M:%S')}",
        "content": content,
        **({"sha": sha} if sha else {})
    }).encode()

    req = urllib.request.Request(api_url, data=payload, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  [GITHUB] Updated OK ({resp.status})")
            return True
    except Exception as e:
        print(f"  [GITHUB] Failed: {e}")
        return False

# ── Load / Save State ─────────────────────────────────────────
STATE_FILE = "monitor_state.json"

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ── Main ──────────────────────────────────────────────────────
def main():
    ts    = datetime.now(tz=__import__("zoneinfo").ZoneInfo("Asia/Karachi")).strftime("%d/%m/%Y, %H:%M:%S")
    now   = time.time()
    state = load_state()
    result = {"updated_at": ts}

    print(f"\n=== MikroTik Monitor === {ts}")

    for router in ROUTERS:
        rid = router["id"]
        print(f"\n--- Router {rid}: {router['name']} ---")
        up_hosts   = []
        down_hosts = []

        for host in router["hosts"]:
            r = check_host(host["ip"], host["port"])
            if r["online"]:
                print(f"  [UP  ] {host['label']} ({host['ip']}:{host['port']}) {r['ms']}ms")
                up_hosts.append({**host, "ms": r["ms"]})
            else:
                print(f"  [DOWN] {host['label']} ({host['ip']}:{host['port']}) — {r['error']}")
                down_hosts.append({**host, "error": r["error"]})

        all_down    = len(up_hosts) == 0
        was_down    = state.get(f"r{rid}_down", False)
        last_alert  = state.get(f"r{rid}_last_alert", 0)
        cooldown_ok = (now - last_alert) >= (COOLDOWN_MIN * 60)

        if all_down:
            print("  *** ALL DOWN ***")
            if not was_down or cooldown_ok:
                html, text = build_email("down", router["name"], down_hosts, up_hosts, ts)
                send_email(f"ROUTER DOWN: {router['name']}", html, text)
                state[f"r{rid}_last_alert"] = now
                state[f"r{rid}_down_since"] = state.get(f"r{rid}_down_since") or now
        elif was_down:
            dur = int((now - state.get(f"r{rid}_down_since", now)) / 60)
            html, text = build_email("restored", router["name"], down_hosts, up_hosts, ts)
            send_email(f"RESTORED: {router['name']} (down {dur} min)", html, text)
            state[f"r{rid}_down_since"] = None
            state[f"r{rid}_last_alert"] = now
        else:
            print("  All OK")

        state[f"r{rid}_down"] = all_down
        result[f"r{rid}_down"]   = all_down
        result[f"r{rid}_status"] = {
            "name":       router["name"],
            "all_down":   all_down,
            "checked_at": ts,
            "up_hosts":   [{"label": h["label"], "ip": h["ip"], "ms": h["ms"]} for h in up_hosts],
            "down_hosts": [{"label": h["label"], "ip": h["ip"], "error": h["error"]} for h in down_hosts],
        }

    save_state(state)
    push_github(result)
    print("\n=== Done ===")

if __name__ == "__main__":
    main()
