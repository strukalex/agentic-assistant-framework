#!/bin/bash
# setup_local_llm.sh
# Quick setup script for running Qwen3-8B locally via Ollama
# This script installs Ollama (if needed) and pulls the Qwen3-8B model

set -e  # Exit on error

echo "================================================"
echo "Local LLM Setup - Qwen3-8B via Ollama"
echo "================================================"

# 1. Check/Install Ollama
echo ""
echo "Step 1: Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama not found. Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "✅ Ollama installed successfully"
else
    echo "✅ Ollama is already installed ($(ollama --version))"
fi

# 2. Start/Check Ollama Server
echo ""
echo "Step 2: Starting Ollama server..."
if ! pgrep -x "ollama" > /dev/null; then
    echo "🚀 Starting Ollama server in background..."
    ollama serve &
    OLLAMA_PID=$!
    echo "   Ollama server started (PID: $OLLAMA_PID)"
    echo "   Waiting for server to be ready..."
    sleep 5

    # Verify server is responding
    MAX_RETRIES=10
    RETRY_COUNT=0
    while ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "❌ Failed to start Ollama server after ${MAX_RETRIES} attempts"
            exit 1
        fi
        echo "   Waiting... (attempt $RETRY_COUNT/$MAX_RETRIES)"
        sleep 2
    done
    echo "✅ Ollama server is ready"
else
    echo "✅ Ollama server is already running"
fi

# 3. Pull Qwen2.5-8B Model
echo ""
echo "Step 3: Pulling Qwen2.5-8B model..."
echo "   This may take several minutes (model size: ~5GB)"
echo "   Progress:"
ollama pull qwen2.5

echo ""
echo "Step 4: Verifying installation..."
ollama list

echo ""
echo "================================================"
echo "✅ Setup Complete!"
echo "================================================"
echo ""
echo "Model 'qwen2.5:8b' is ready at http://localhost:11434"
echo ""
echo "To use this model with your agent:"
echo "  1. Add to .env: LLM_PROVIDER=local"
echo "  2. Run your agent - it will automatically use the local model"
echo ""
echo "To test the model directly:"
echo "  ollama run qwen2.5:8b"
echo ""
echo "To stop Ollama:"
echo "  pkill ollama"
echo ""
