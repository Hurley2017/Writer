#!/bin/bash
# Quick status check for the Writer project
# Usage: bash status.sh

echo "╔════════════════════════════════════════════════════════╗"
echo "║        WRITER PROJECT - REMOTE STATUS CHECK            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check Ollama
echo "🔷 OLLAMA SERVER"
echo "─────────────────────────────────────────────────────────"
if pgrep -x "ollama" > /dev/null; then
    echo "✓ Ollama process running"
    OLLAMA_STATUS=$(curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -m json.tool 2>/dev/null)
    if [ $? -eq 0 ]; then
        MODELS=$(echo "$OLLAMA_STATUS" | grep '"name"' | wc -l)
        echo "✓ Ollama API reachable"
        echo "✓ Models loaded: $MODELS"
        echo "$OLLAMA_STATUS" | grep -o '"name": "[^"]*' | head -3
    else
        echo "✗ Ollama API not reachable (port 11434)"
    fi
else
    echo "✗ Ollama not running (use: ollama serve)"
fi
echo ""

# Check GPU/VRAM
echo "🎮 GPU STATUS"
echo "─────────────────────────────────────────────────────────"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader,nounits | awk '{print "GPU: " $1 "\nMemory: " $2 "MB total, " $3 "MB used, " $4 "MB free"}'
else
    echo "No NVIDIA GPU detected"
fi
echo ""

# Check memory
echo "💾 SYSTEM MEMORY"
echo "─────────────────────────────────────────────────────────"
free -h | awk 'NR==2 {print "Memory: " $2 " total, " $3 " used, " $4 " free"}'
echo ""

# Check disk
echo "💿 DISK USAGE"
echo "─────────────────────────────────────────────────────────"
echo "Project: $(du -sh /home/tusher/Writer 2>/dev/null | cut -f1)"
echo "Output files: $(du -sh /home/tusher/Writer/output 2>/dev/null | cut -f1 || echo 'none')"
echo "Model cache: $(du -sh /home/tusher/hf_cache 2>/dev/null | cut -f1 || echo 'none')"
echo ""

# Check recent activity
echo "📝 RECENT OUTPUT FILES"
echo "─────────────────────────────────────────────────────────"
if [ -d "/home/tusher/Writer/output" ]; then
    find /home/tusher/Writer/output -type f -mtime -1 -exec ls -lh {} \; | awk '{print $9, "(" $5 ")"}' | tail -5
else
    echo "No output directory yet"
fi
echo ""

# Check recent logs
echo "📋 RECENT LOGS"
echo "─────────────────────────────────────────────────────────"
if ls /home/tusher/Writer/*.log 2>/dev/null | head -3; then
    echo "Latest log lines:"
    tail -n 3 /home/tusher/Writer/*.log 2>/dev/null | head -10
else
    echo "No log files yet"
fi
echo ""

echo "╚════════════════════════════════════════════════════════╝"
