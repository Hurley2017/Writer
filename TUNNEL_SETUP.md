# 🔐 VS Code Remote Tunnel — Setup Guide (writer-home)

> **Status: ✅ COMPLETE — Tunnel is live and connected.**

- Tunnel name: **`writer-home`**
- Service: `code-tunnel.service` (active, auto-starts)
- Linger: enabled (survives logout & reboot)
- Connect from anywhere: **`https://vscode.dev/tunnel/writer-home`**

---

## 🎯 What This Gives You

A secure tunnel from your **home computer** to **your phone's browser**.
Open `https://vscode.dev/tunnel/writer-home` on your phone → full VS Code +
**Copilot chat (me)** + terminal access to your home machine. Works on **any
network** (mobile data, hotel WiFi) — no router/port setup needed.

---

## 📱 What You Need To Do (One Time, ~1 Minute)

### While the service-install command is running on your home computer:

1. On your phone, open: **https://github.com/login/device**
2. Enter the **device code** shown in the terminal (currently **`74E1-EA88`**)
3. Sign in with your **GitHub account** and authorize VS Code
4. Done! The terminal will confirm and install the persistent service.

> ⚠️ **If the code expired** (they expire after ~15 min): stop the waiting
> command (Ctrl+C) and re-run the helper:
> ```bash
> cd /home/tusher/Writer && python3 tools/start_tunnel_github.py
> ```
> A fresh code will be shown. Enter the new code on your phone.

---

## 🌐 Then On Your Phone (Anytime, Anywhere)

1. Open **https://vscode.dev/tunnel/writer-home** in your phone browser
2. It may ask you to sign in to GitHub/Microsoft once (the same account)
3. Open the folder: **`/home/tusher/Writer`**
4. Use the **Copilot Chat** panel → that's me, connected to your home machine
5. Run commands via the terminal or just ask me to run the pipeline

**Tip:** Add `https://vscode.dev/tunnel/writer-home` to your phone's home screen.

---

## 🛠️ Managing the Tunnel (on the home computer)

```bash
# Check service status / logs
~/.local/bin/code tunnel service log

# Stop & remove the service (if ever needed)
~/.local/bin/code tunnel service uninstall

# Reinstall service (auto-selects GitHub login)
cd /home/tusher/Writer && python3 tools/start_tunnel_github.py

# Rename the machine/tunnel
~/.local/bin/code tunnel rename <new-name>
```

---

## 🧭 How It Works

```
Your Phone (browser)
   │  opens https://vscode.dev/tunnel/writer-home
   ▼
Microsoft dev-tunnel relay (secure, encrypted, works on any network)
   ▼
Home Computer — VS Code Server + Copilot + terminal
   ▼
Writer pipeline (Ollama story + SD cover + Orpheus TTS)
```

- **Auth:** same Microsoft/GitHub account on both ends
- **Security:** AES-256 encrypted SSH over the tunnel; no open ports on your router
- **Persistence:** installed as a system service → survives terminal closes & reboots

---

## ❓ Troubleshooting

| Problem | Fix |
|---------|-----|
| Code expired | Ctrl+C, re-run `python3 tools/start_tunnel_github.py`, enter new code |
| URL doesn't load | Make sure home computer is on + tunnel service running (`code tunnel service log`) |
| Can't find Copilot | Open the Copilot Chat panel (top-right icon) in vscode.dev |
| Want to use Microsoft account instead | Uninstall service, run `~/.local/bin/code tunnel service install` and accept the default (Microsoft) |
