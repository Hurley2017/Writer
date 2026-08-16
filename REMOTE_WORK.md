# Remote Work Guide: Writer Project on Mobile

## 🔄 How to Work on This Project Remotely

You have several options to continue this project while away from home:

---

## Option 1: **VS Code Remote Tunnels** 🥇 (RECOMMENDED — works anywhere, no router setup)

Full VS Code + **Copilot chat** + terminal on your phone browser, connected to
your home machine through a secure Microsoft tunnel. Works on **any network**
(mobile data, hotel WiFi) — no port forwarding needed.

### Setup (already 90% done — see [TUNNEL_SETUP.md](TUNNEL_SETUP.md)):
1. Complete the **one-time login** shown in the `service install` terminal (see TUNNEL_SETUP.md)
2. On your phone, open: **`https://vscode.dev/tunnel/writer-home`**
3. Open folder `/home/tusher/Writer` and use Copilot Chat

### Workflow:
```
Phone browser → vscode.dev/tunnel/writer-home → Home computer (Copilot + terminal)
```

---

## Option 2: **VS Code Remote SSH** (Alternative)

### Setup on Home Computer (Do This Now)
```bash
# Install OpenSSH server
echo '1234' | sudo -S apt-get install -y openssh-server
echo '1234' | sudo -S systemctl start ssh
echo '1234' | sudo -S systemctl enable ssh

# Get your home computer's IP
hostname -I
# Note this IP (e.g., 192.168.1.100 or similar)
```

### On Mobile (via Browser or App)
1. **Option A: VS Code Web** (No app needed)
   - Go to: https://vscode.dev
   - Install "Remote SSH" extension
   - Connect to: `ssh://tusher@192.168.1.100:/home/tusher/Writer`
   - Browse files and chat with me in Copilot

2. **Option B: VS Code Mobile App**
   - Download "VS Code" app on phone
   - Connect via SSH same way

### Workflow:
```
Mobile → VS Code SSH → Home Computer → Run Commands
         ↓
      Chat with me in Copilot Chat
         ↓
      See output, share logs
```

---

## Option 3: **Terminal Sharing via Web** (Quickest)

### Setup on Home Computer (Do Now)
```bash
# Install gotty (terminal in browser)
cd /tmp
wget https://github.com/yudai/gotty/releases/download/v1.0.1/gotty_linux_amd64.tar.gz
tar xzf gotty_linux_amd64.tar.gz
sudo mv gotty /usr/local/bin/

# Run in Writer project directory
cd /home/tusher/Writer
gotty bash
# Note the URL it shows (e.g., http://192.168.1.100:8080)
```

### On Mobile
- Open browser
- Go to: `http://192.168.1.100:8080` (or IP shown above)
- Full terminal in browser, run commands live
- Switch to this chat to discuss output

---

## Option 4: **Log Files + Chat** (Asynchronous, No Setup)

### Before You Leave (Do This Now)

Create a log capture script:
```bash
cat > /home/tusher/Writer/run_with_log.sh << 'SCRIPTEOF'
#!/bin/bash
LOG_FILE="/home/tusher/Writer/pipeline_log_$(date +%Y%m%d_%H%M%S).txt"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Writer Pipeline Started: $(date) ===" 
cd /home/tusher/Writer
source venv/bin/activate

# Run the pipeline
python -m src.pipeline \
  --genre fantasy \
  --topic "a young wizard learning fire magic" \
  --length short \
  --stage all

echo "=== Pipeline Finished: $(date) ==="
echo "Logs saved to: $LOG_FILE"
SCRIPTEOF

chmod +x /home/tusher/Writer/run_with_log.sh
```

Then when you're away:
1. **Ask me to run:**
   > "Run the pipeline with these parameters: fantasy genre, 'young wizard' topic, short length"

2. **I execute:**
   ```bash
   cd /home/tusher/Writer && source venv/bin/activate
   bash run_with_log.sh
   ```

3. **I share the log file content with you**

4. **You review and respond** via this chat

---

## Option 5: **Scheduled Remote Execution**

### Setup (Do Before Leaving)
```bash
# Create a background pipeline runner
cat > /home/tusher/Writer/scheduled_pipeline.sh << 'SCHEDEOF'
#!/bin/bash
cd /home/tusher/Writer
source venv/bin/activate

LOG_FILE="logs/pipeline_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

{
    echo "Starting at $(date)"
    python -m src.pipeline --genre fantasy --topic "test" --length short --stage all
    echo "Finished at $(date)"
} > "$LOG_FILE" 2>&1

echo "Output saved to: $LOG_FILE"
SCHEDEOF

chmod +x /home/tusher/Writer/scheduled_pipeline.sh

# Test it works
bash /home/tusher/Writer/scheduled_pipeline.sh
```

Then from mobile:
1. **Ask me:** "Run the scheduled pipeline"
2. **I execute it** in background
3. **Check progress** by asking: "Show me the latest log"

---

## **📱 What to Do Right Now (Before Leaving)**

### Step 1: Start Ollama Server (Keep Running)
```bash
# In a terminal on your home computer (don't close it):
cd /home/tusher/Writer
ollama serve
# Keep this open in background or use:
nohup ollama serve > /tmp/ollama.log 2>&1 &
```

### Step 2: Download the Story Model
```bash
# In another terminal:
ollama pull nous-hermes2:10.7b-solar-q6_K
# This takes ~15 minutes, ~9GB download
# Wait for it to finish completely
```

### Step 3: Create Test Command Log
```bash
cat > /home/tusher/Writer/MOBILE_COMMANDS.md << 'CMDEOF'
# Commands to Run While Away

## Quick Status Check
```bash
cd /home/tusher/Writer && source venv/bin/activate
python3 << 'TEST'
from src.lmstudio import LMStudio
import json
cfg = json.load(open('config.json'))
lm = LMStudio(cfg['lmstudio']['base_url'])
print("✓ Ollama Connected" if lm.is_available() else "✗ Ollama NOT running")
print(f"Model ready: {cfg['lmstudio']['model']}")
TEST
```

## Run Full Pipeline
```bash
cd /home/tusher/Writer && source venv/bin/activate
python -m src.pipeline \
  --genre fantasy \
  --topic "a test story" \
  --length short \
  --stage all 2>&1 | tee pipeline_output.log
```

## Just Test Story Generation
```bash
cd /home/tusher/Writer && source venv/bin/activate
python3 << 'STORYTEST'
from src.lmstudio import LMStudio
from src.storygen import StoryGenerator
from src.config import load_config
import json

cfg = load_config()
lm = LMStudio(cfg['lmstudio']['base_url'])
gen = StoryGenerator(lm, cfg['lmstudio']['model'], cfg)

outline = gen.generate_outline(
    genre="fantasy",
    topic="a wizard",
    tone="epic",
    length="short"
)
print(json.dumps(outline, indent=2))
STORYTEST
```

## Check Ollama Status
```bash
curl http://localhost:11434/api/tags
```

## See Available Disk Space
```bash
du -sh /home/tusher/Writer/output
df -h /home/tusher
```

CMDEOF
cat /home/tusher/Writer/MOBILE_COMMANDS.md
```

### Step 4: Create Status Monitoring Script
```bash
cat > /home/tusher/Writer/status.sh << 'STATUSEOF'
#!/bin/bash
echo "=== WRITER PROJECT STATUS ==="
echo "Time: $(date)"
echo ""
echo "--- Ollama Status ---"
curl -s http://localhost:11434/api/tags | python3 -m json.tool 2>/dev/null || echo "Ollama not running"
echo ""
echo "--- Disk Usage ---"
du -sh /home/tusher/Writer/output 2>/dev/null || echo "No output yet"
echo ""
echo "--- Recent Logs ---"
ls -lht /home/tusher/Writer/*.log 2>/dev/null | head -3 || echo "No logs yet"
echo ""
echo "--- Process Check ---"
pgrep ollama > /dev/null && echo "✓ Ollama running" || echo "✗ Ollama not running"
STATUSEOF

chmod +x /home/tusher/Writer/status.sh
```

### Step 5: Make SSH Easier (Optional but Recommended)
```bash
# On your home computer
cat >> ~/.bashrc << 'SSHEOF'
alias writer-status="cd /home/tusher/Writer && bash status.sh"
alias writer-logs="tail -f /home/tusher/Writer/pipeline_*.log"
SSHEOF

source ~/.bashrc
```

---

## **📱 How to Communicate on Mobile**

### Method A: Direct SSH via VS Code
1. Open VS Code on mobile (app or web)
2. Connect to home computer via SSH
3. Open Terminal in VS Code
4. Run commands
5. Chat with me in Copilot Chat panel

### Method B: This Chat + Log Sharing
1. **You ask me:** "Run the status check and show me results"
2. **I run:** `bash /home/tusher/Writer/status.sh`
3. **I paste output** in this chat
4. **You review** and give next instructions

### Method C: Output Files
1. Ollama keeps **logs in background** while running
2. Pipeline saves **output to `/home/tusher/Writer/output/`**
3. **You ask:** "Check latest output files"
4. **I read** and report back

---

## **🔄 Asynchronous Workflow Example**

**You (Mobile, 9 AM):**
> "Hey, before I left I set up everything. Can you run the full story pipeline with a fantasy theme? Use 'young wizard' as topic, short length. Let me know when it's done and show me the generated files."

**Me (Running on home computer):**
```bash
cd /home/tusher/Writer && source venv/bin/activate
time python -m src.pipeline \
  --genre fantasy \
  --topic "young wizard" \
  --length short \
  --stage all
```

**Me (After ~15 min):**
> "✓ Pipeline completed! Generated files:
> - /home/tusher/Writer/output/young_wizard-SHORT.pdf
> - /home/tusher/Writer/output/cover_verify.png
> - Duration: 12 minutes 34 seconds
> Ready for your review!"

**You (Mobile, Later):**
> "Great! How's the story quality? Can you also run it one more time with a longer length and different topic?"

**Me:**
> Running with new params...

---

## **✅ Quick Checklist Before You Leave**

- [ ] Ollama installed and `ollama serve` running
- [ ] Model downloaded: `nous-hermes2:10.7b-solar-q6_K`
- [ ] Created `/home/tusher/Writer/MOBILE_COMMANDS.md`
- [ ] Created `/home/tusher/Writer/status.sh`
- [ ] Created `/home/tusher/Writer/run_with_log.sh`
- [ ] Tested Ollama connection once
- [ ] Terminal or SSH access ready

---

## **📋 Important Paths to Know**

```
Project root:        /home/tusher/Writer
Config:              /home/tusher/Writer/config.json
Output (generated):  /home/tusher/Writer/output/
Cache (models):      /home/tusher/hf_cache/
Logs:                /home/tusher/Writer/*.log (created during runs)
```

---

## **💡 Pro Tips**

1. **Long-running tasks:**
   - Use `nohup` to keep processes running if SSH disconnects
   - Use `screen` or `tmux` for persistent sessions

2. **Monitoring without SSH:**
   - I can check `tail -f /tmp/ollama.log` for Ollama status
   - I can list output files with `ls -la output/`

3. **Battery/Data:**
   - Use logging approach (Option 3) if mobile data is limited
   - SSH terminal uses minimal bandwidth after connection

4. **Resume on Return:**
   - Everything is idempotent - can re-run any command
   - Output files are timestamped, safe to regenerate

---

**Ready to set up remote access? Which option do you prefer?**
- Option 1: VS Code SSH (full IDE access)
- Option 2: Terminal in browser (quickest)
- Option 3: Async via chat + logs (simplest, no extra setup)
- Option 4: Scheduled execution (fire and forget)
