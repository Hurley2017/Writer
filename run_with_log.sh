#!/bin/bash
# Run the Writer pipeline with full logging
# Usage: bash run_with_log.sh [genre] [topic] [length]

PROJECT_DIR="/home/tusher/Writer"
cd "$PROJECT_DIR"

# Default values
GENRE="${1:-fantasy}"
TOPIC="${2:-a young wizard learning fire magic}"
LENGTH="${3:-short}"

# Create log filename
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/pipeline_$(date +%Y%m%d_%H%M%S).log"

echo "Starting Writer Pipeline"
echo "Genre: $GENRE"
echo "Topic: $TOPIC"
echo "Length: $LENGTH"
echo "Log file: $LOG_FILE"
echo ""

# Start logging
{
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║           WRITER PIPELINE - DETAILED LOG                 ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Genre: $GENRE"
    echo "Topic: $TOPIC"
    echo "Length: $LENGTH"
    echo ""
    
    source venv/bin/activate
    
    time python -m src.pipeline \
        --genre "$GENRE" \
        --topic "$TOPIC" \
        --length "$LENGTH" \
        --stage all
    
    STATUS=$?
    
    echo ""
    echo "Finished at: $(date '+%Y-%m-%d %H:%M:%S')"
    if [ $STATUS -eq 0 ]; then
        echo "✓ Pipeline completed successfully"
        echo ""
        echo "Output files:"
        ls -lh "$PROJECT_DIR/output/" 2>/dev/null | grep -v "^total" | awk '{print "  " $9 " (" $5 ")"}'
    else
        echo "✗ Pipeline failed with exit code: $STATUS"
    fi
    
} | tee "$LOG_FILE"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Log saved to: $LOG_FILE"
echo "═══════════════════════════════════════════════════════════"
