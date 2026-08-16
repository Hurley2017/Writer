# 🚀 QUICK START: Writer Project Remote Setup

## **Right Now (Before You Leave)**

### The One-Minute Version:
1. Download Ollama from https://ollama.ai/download
2. Run: `ollama serve` (keep this terminal open)
3. In another terminal: `ollama pull nous-hermes2:10.7b-solar-q6_K`
4. Run: `bash test_ollama.sh` → verify everything works
5. Leave! The setup is ready.

### Then on Mobile:
- Chat with me here in Copilot
- I'll run commands on your home computer
- You get real-time results

---

## **Full Setup Details**

See: [BEFORE_LEAVING.md](BEFORE_LEAVING.md)

---

## **Remote Work Options**

1. **Simple Chat + Logs** (Easiest)
   - You: "Run the pipeline with X parameters"
   - Me: Runs it, shares output
   - No extra setup needed

2. **VS Code SSH** (Most Control)
   - Full IDE on mobile via SSH
   - See REMOTE_WORK.md for setup

3. **Terminal in Browser** (Quick Access)
   - Web-based terminal via gotty
   - See REMOTE_WORK.md for setup

---

## **Key Files**

| File | Purpose |
|------|---------|
| `BEFORE_LEAVING.md` | **START HERE** - Pre-departure checklist |
| `REMOTE_WORK.md` | How to work on mobile |
| `MODEL_RESEARCH.md` | Why Nous Hermes 2 Solar 10.7B for stories |
| `status.sh` | Check system status remotely |
| `test_ollama.sh` | Verify Ollama is working |
| `run_with_log.sh` | Run pipeline with logging |

---

## **Pipeline Overview**

```
Stage 1: Story (Nous Hermes 2 Solar 10.7B) → 10-20 min
  ├─ Outline generation
  ├─ Chapter generation
  └─ Saves to story.json

Stage 2: Images (SD 1.5) → ~2 min
  └─ Generates book cover

Stage 3: Audio (Orpheus 3B 4-bit) → 3-5 min
  └─ Narrates chapters with emotion

Output: output/<title>/ with PDF + audio + metadata
```

---

## **How to Use While Away**

### Command Format:
Send me a message like:
```
"Run the full pipeline:
- Genre: fantasy
- Topic: a young mage learning fire magic  
- Length: short"
```

### I'll Execute:
```bash
cd /home/tusher/Writer && source venv/bin/activate
bash run_with_log.sh "fantasy" "a young mage learning fire magic" "short"
```

### You Get:
- Real-time progress updates
- Complete log when done
- List of generated files
- Ready for next iteration

---

## **System Specs (Your Hardware)**

- **CPU**: Full cores available during story gen
- **RAM**: 16 GB (Story model uses 12-14 GB)
- **GPU**: GTX 1060 6GB (Image gen: 2.06 GB, TTS: 2-3 GB)
- **Storage**: ~500 KB project + models cache

---

## **Troubleshooting Quick Reference**

| Problem | Solution |
|---------|----------|
| Ollama not found | `ollama pull nous-hermes2:10.7b-solar-q6_K` |
| Port 11434 in use | Kill with `killall ollama` and retry |
| Out of memory | One model at a time (automatic) |
| Slow generation | Normal for 13B model on CPU (~30-60 sec/prompt) |
| Test failed | Run `bash test_ollama.sh` and send me output |

---

## **Expected Performance**

- **Story generation**: 30-60 seconds per prompt
- **Full 5-chapter story**: 3-5 minutes
- **Image cover**: ~2 minutes
- **Audio narration**: ~30-60 sec per chapter
- **Total for short story**: 10-15 minutes

---

**Ready? Start with [BEFORE_LEAVING.md](BEFORE_LEAVING.md)**
