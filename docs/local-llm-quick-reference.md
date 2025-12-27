# Local LLM Quick Reference

Quick commands for managing local LLMs with Ollama.

## Initial Setup

```bash
# One-time setup (installs Ollama + pulls Qwen2.5-8B)
./scripts/setup_local_llm.sh

# Configure environment
echo "LLM_PROVIDER=local" >> .env

# Test installation
python scripts/test_local_llm.py
```

## Common Commands

### Server Management
```bash
# Start Ollama server
ollama serve &

# Check if running
pgrep ollama

# Stop server
pkill ollama
```

### Model Management
```bash
# List installed models
ollama list

# Pull a new model
ollama pull qwen2.5:8b

# Remove a model
ollama rm qwen2.5:8b

# Show model details
ollama show qwen2.5:8b
```

### Testing Models
```bash
# Interactive chat
ollama run qwen2.5:8b

# Single question
ollama run qwen2.5:8b "What is Python?"

# Test with your agent
python scripts/test_local_llm.py
```

## Switching Models

```bash
# Pull new model
ollama pull llama3.1:8b

# Update .env
echo "LLM_MODEL_NAME=llama3.1:8b" >> .env

# Verify
python scripts/test_local_llm.py
```

## Environment Variables

```bash
# .env file for local LLM
LLM_PROVIDER=local
LLM_MODEL_NAME=qwen2.5:8b
LLM_BASE_URL=http://localhost:11434/v1

# Optional tuning
LLM_TEMPERATURE=0.4
LLM_MAX_TOKENS=4096
```

## Popular Models

| Model | Size | Pull Command | Use Case |
|-------|------|--------------|----------|
| qwen2.5:8b | 5GB | `ollama pull qwen2.5:8b` | General (default) |
| llama3.1:8b | 5GB | `ollama pull llama3.1:8b` | Alternative |
| mistral:7b | 4GB | `ollama pull mistral:7b` | Faster/smaller |
| qwen2.5:14b | 9GB | `ollama pull qwen2.5:14b` | More capable |
| deepseek-r1:8b | 5GB | `ollama pull deepseek-r1:8b` | Code-focused |

## Troubleshooting

### Connection Refused
```bash
# Check if running
pgrep ollama || ollama serve &
sleep 5
```

### Model Not Found
```bash
# List installed
ollama list

# Pull if missing
ollama pull qwen2.5:8b
```

### Slow Performance
```bash
# Check GPU usage
ollama ps

# Reduce max tokens in .env
LLM_MAX_TOKENS=2048
```

### Out of Memory
```bash
# Use smaller model
ollama pull mistral:7b
echo "LLM_MODEL_NAME=mistral:7b" >> .env
```

## Switch Back to Azure

```bash
# Update .env
echo "LLM_PROVIDER=azure" >> .env

# Verify Azure credentials are set
grep AZURE .env
```

## Custom Model Configuration

```bash
# Create custom Modelfile
cat > Modelfile <<EOF
FROM qwen2.5:8b
PARAMETER temperature 0.4
PARAMETER num_ctx 16384
SYSTEM You are a helpful research assistant.
EOF

# Build custom model
ollama create my-researcher -f Modelfile

# Use custom model
echo "LLM_MODEL_NAME=my-researcher" >> .env
```

## System Requirements

**Minimum:**
- 8GB RAM
- 10GB disk space
- Linux, macOS, or WSL2

**Recommended:**
- 16GB+ RAM
- 20GB+ disk space
- NVIDIA GPU with 8GB+ VRAM

## Links

- Full Guide: [docs/local-llm-setup.md](./local-llm-setup.md)
- Ollama Docs: https://github.com/ollama/ollama
- Model Library: https://ollama.com/library
