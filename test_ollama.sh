#!/bin/bash
# Test Ollama connection and model availability
# Quick diagnostic for remote troubleshooting

echo "Testing Ollama Connection..."
echo ""

# Test 1: Check if Ollama is running
echo "1. Checking if Ollama process is running..."
if pgrep -x "ollama" > /dev/null; then
    echo "   ✓ Ollama process found"
else
    echo "   ✗ Ollama not running"
    echo "   Solution: Run 'ollama serve' in another terminal"
    exit 1
fi
echo ""

# Test 2: Check API endpoint
echo "2. Checking Ollama API endpoint (http://localhost:11434)..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "   ✓ API endpoint reachable"
else
    echo "   ✗ API endpoint not reachable"
    echo "   Solution: Make sure Ollama is running and port 11434 is open"
    exit 1
fi
echo ""

# Test 3: List models
echo "3. Checking available models..."
MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys, json; data=json.load(sys.stdin); print('\n   '.join([m['name'] for m in data.get('models', [])]))" 2>/dev/null)
if [ -z "$MODELS" ]; then
    echo "   ✗ No models found"
    echo "   Solution: Run 'ollama pull nous-hermes2:10.7b-solar-q6_K'"
    exit 1
else
    echo "   ✓ Models found:"
    echo "   $MODELS"
fi
echo ""

# Test 4: Test via Python client
echo "4. Testing via Python LMStudio client..."
cd /home/tusher/Writer && source venv/bin/activate

python3 << 'PYEOF'
import json
from src.lmstudio import LMStudio

try:
    cfg = json.load(open('config.json'))
    lm = LMStudio(cfg['lmstudio']['base_url'])
    
    if lm.is_available():
        print("   ✓ Python client connected")
        models = lm.list_models()
        print(f"   ✓ Models available: {models}")
        
        # Quick test message
        print("\n5. Testing chat completion...")
        response = lm.chat(
            messages=[{"role": "user", "content": "Say 'Ollama is working!' in exactly those words"}],
            model=cfg['lmstudio']['model'],
            temperature=0.7,
            max_tokens=50
        )
        print(f"   ✓ Response: {response[:80]}")
        print("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
    else:
        print("   ✗ Python client cannot connect")
        print("   Suggestion: Check if 'ollama serve' is running")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "═══════════════════════════════════════════════════════════"
