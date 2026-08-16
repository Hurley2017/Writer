# ✅ PRE-DEPARTURE CHECKLIST

## What You Need to Do Before Leaving Home

Follow these steps in order. Estimated time: **30-40 minutes**

---

## **STEP 1: Download Ollama** ⏱️ ~5 minutes

Visit: https://ollama.ai/download

Choose **Linux** and download the binary.

```bash
# Extract it (adjust path to where you downloaded)
tar -xzf ~/Downloads/ollama-*-linux-amd64.tar.gz

# Move to system path (optional, or use full path)
sudo mv ollama/bin/ollama /usr/local/bin/
```

Verify:
```bash
ollama --version
# Should print version number
```

---

## **STEP 2: Start Ollama Server** ⏱️ Immediate

**Open a NEW terminal window and keep it open** (this is critical - Ollama must stay running):

```bash
ollama serve
```

You should see:
```
Ollama is running at http://localhost:11434
```

✅ **Leave this terminal running while you set up everything else**

---

## **STEP 3: Download the Story Model** ⏱️ ~15-20 minutes

**In another terminal window** (not the ollama serve one):

```bash
# This downloads ~9GB, takes 10-15 minutes
ollama pull nous-hermes2:10.7b-solar-q6_K

# Wait for "100% complete" message
```

Verify it's downloaded:
```bash
ollama list
# Should show: nous-hermes2:10.7b-solar-q6_K
```

---

## **STEP 4: Test Everything** ⏱️ ~5 minutes

Still in the same terminal (or a new one), run:

```bash
cd /home/tusher/Writer
bash test_ollama.sh
```

Expected output:
```
✓ Ollama process found
✓ API endpoint reachable  
✓ Models found: nous-hermes2
✓ Python client connected
✓ Response: Ollama is working!

✓✓✓ ALL TESTS PASSED ✓✓✓
```

---

## **STEP 5: Prepare for Remote Access** ⏱️ ~5 minutes

### Option A: SSH Remote Access (Recommended)

```bash
# Check if SSH is installed
echo '1234' | sudo -S apt-get install -y openssh-server

# Start SSH service
echo '1234' | sudo -S systemctl start ssh
echo '1234' | sudo -S systemctl enable ssh

# Get your home computer's IP address
hostname -I
# Write down this IP (e.g., 192.168.1.100)
```

On your mobile device, you can now connect via SSH:
- App: VS Code (iOS/Android) + Remote SSH extension
- Or: Browser terminal via `gotty` (see REMOTE_WORK.md)

### Option B: Keep Ollama Running in Background (Simplest)

```bash
# This keeps ollama running even if you close terminal
nohup ollama serve > /tmp/ollama.log 2>&1 &

# Verify it's running
sleep 2
ps aux | grep ollama
```

---

## **STEP 6: Quick Status Check** ⏱️ ~1 minute

Before you leave, run one final check:

```bash
cd /home/tusher/Writer
bash status.sh
```

Should show:
```
✓ Ollama process running
✓ Models loaded: 1
✓ GPU: NVIDIA GeForce GTX 1060 6GB
✓ Memory: 16G total, X used, Y free
```

---

## **STEP 7: You're Ready!** 🎉

Now you can:

1. **On Mobile:** Ask me to run commands
2. **I'll execute** them on your home computer
3. **I'll share results** and logs in this chat
4. **You decide** next steps from mobile

---

## ✅ Pre-Departure Checklist

- [ ] Downloaded Ollama
- [ ] Ollama server running (`ollama serve`)
- [ ] Model downloaded (`nous-hermes2:10.7b-solar-q6_K`)
- [ ] Ran `bash test_ollama.sh` → All tests passed
- [ ] SSH installed (optional, for mobile access)
- [ ] Ran `bash status.sh` → Everything looks good
- [ ] Noted your home computer's IP address (if using SSH)

---

## 📱 When You're Away on Mobile

### Simple Approach (No Setup):

Just message me in this Copilot Chat:

> "Run the full pipeline with fantasy genre, 'a lost princess' topic, short length"

I'll:
1. Execute the command
2. Wait for completion (~10-15 min)
3. Share results and output files
4. You give me next instructions

### Advanced Approach (Live Terminal):

If you set up SSH (recommended):

1. Open VS Code on mobile
2. Connect via SSH to your home computer
3. Have a live terminal
4. Chat with me about what to try next

---

## 🆘 If Something Goes Wrong

If you're away and something fails:

1. **Send me this info:**
   ```bash
   bash status.sh
   bash test_ollama.sh
   tail -f /tmp/ollama.log  # Last lines of ollama log
   ```

2. **I'll diagnose** based on output

3. **Most common fixes:**
   - Ollama crashed: `ollama serve` again
   - Model not downloaded: `ollama pull nous-hermes2:10.7b-solar-q6_K`
   - Port conflicts: Check `netstat -tulpn | grep 11434`

---

## 📞 Contact Points

You can reach me through:
1. **This Copilot Chat** (best option)
2. Share terminal output/logs
3. I'll run commands and report back

---

## 🚀 Example: Remote Pipeline Run

**You (9 AM, on mobile):**
> "Hi! I left everything set up. Can you run the full pipeline with 'fantasy' genre and 'young wizard' topic, short length? Let me know when done."

**Me (5 minutes in):**
> "Running... started at 9:05 AM. Stage 1 (Story): generating outline..."

**Me (12 minutes later):**
> "✓ Pipeline complete! Generated:
> - Story PDF with cover
> - Audiobook narration (3 min 47 sec)
> - Total time: 12 min 34 sec
> Files saved to /output/. Ready for next run?"

**You (checking on mobile):**
> "Awesome! Run it once more with a mystery genre, 'detective story' topic, medium length"

**Me:**
> Starting new run...

---

**You're all set! Ready to proceed with setup?**
