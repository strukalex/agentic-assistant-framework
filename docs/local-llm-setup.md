# Local LLM Setup Guide

This guide explains how to set up and use local LLM models (like Qwen3-8B) with your agent instead of Azure AI Foundry.

## Overview

The project supports two LLM providers:
- **Azure AI Foundry** (default): Cloud-based models via Microsoft Azure
- **Local Ollama**: Run models locally on your machine for privacy and cost savings

## Quick Setup

### 1. Install and Configure Ollama

Run the automated setup script:

```bash
./scripts/setup_local_llm.sh
```

This script will:
- Install Ollama (if not already installed)
- Start the Ollama server
- Pull the Qwen2.5-8B model (~5GB download)
- Verify the installation

### 2. Configure Environment

Update your `.env` file to use the local provider:

```bash
# Switch to local LLM provider
LLM_PROVIDER=local

# Optional: Change model (default is qwen2.5:8b)
LLM_MODEL_NAME=qwen2.5:8b

# Optional: Change Ollama API endpoint (default is http://localhost:11434/v1)
LLM_BASE_URL=http://localhost:11434/v1
```

### 3. Start Using Local Models

Your agent will now automatically use the local model. No code changes needed!

```python
from paias.agents.researcher import run_researcher_agent
from paias.core.memory import MemoryManager

# Works with both Azure and local models - provider is configured via .env
memory = MemoryManager(...)
result = await run_researcher_agent("What is Qwen?", memory)
```

## Architecture Integration

### How It Works

The local LLM integration follows the existing architecture (Constitution Article II.I):

1. **Configuration Layer** ([paias/core/config.py](../paias/core/config.py))
   - Adds `llm_provider`, `llm_model_name`, and `llm_base_url` settings
   - Read from environment variables via Pydantic Settings

2. **LLM Factory** ([paias/core/llm.py](../paias/core/llm.py))
   - `get_azure_model()` function now supports both providers
   - Checks `LLM_PROVIDER` env var to determine which backend to use
   - Returns OpenAI-compatible interface for both Azure and Ollama

3. **Agent Layer** ([paias/agents/researcher.py](../paias/agents/researcher.py))
   - No changes needed - uses `get_azure_model()` factory
   - Automatically works with whichever provider is configured

### Why Ollama?

Based on 2025 industry research:

1. **Industry Standard**: Most widely used tool for local LLM management
2. **OpenAI-Compatible API**: Seamless integration with existing Pydantic AI code
3. **Automatic Model Management**: Handles downloading, running, and updating models
4. **Resource Efficient**: Optimized inference with quantization support
5. **Easy Installation**: Single-command setup on Linux, macOS, and Windows

## Available Models

Ollama supports many models. Some popular options:

| Model | Size | Use Case | Command |
|-------|------|----------|---------|
| qwen2.5:8b | 5GB | General research (recommended) | `ollama pull qwen2.5:8b` |
| qwen2.5:14b | 9GB | Better reasoning, more context | `ollama pull qwen2.5:14b` |
| llama3.1:8b | 5GB | Strong general-purpose alternative | `ollama pull llama3.1:8b` |
| mistral:7b | 4GB | Fast, lightweight | `ollama pull mistral:7b` |
| deepseek-r1:8b | 5GB | Code-focused tasks | `ollama pull deepseek-r1:8b` |

To switch models:
```bash
# 1. Pull the new model
ollama pull llama3.1:8b

# 2. Update .env
LLM_MODEL_NAME=llama3.1:8b
```

## System Requirements

### Minimum
- **RAM**: 8GB (for 8B parameter models)
- **Storage**: 10GB free space
- **OS**: Linux (WSL2), macOS, Windows

### Recommended
- **RAM**: 16GB+ (for 14B+ parameter models)
- **GPU**: NVIDIA GPU with 8GB+ VRAM (for faster inference)
- **Storage**: 20GB+ free space (for multiple models)

## Performance Considerations

### Context Window
- Qwen2.5 supports up to 128k tokens context
- Ollama defaults to 2048 tokens for performance
- To increase context window, create a custom Modelfile:

```bash
# Create custom model with larger context
ollama create qwen2.5-32k -f - <<EOF
FROM qwen2.5:8b
PARAMETER num_ctx 32768
EOF

# Update .env to use custom model
LLM_MODEL_NAME=qwen2.5-32k
```

### GPU Acceleration
Ollama automatically uses GPU if available:
```bash
# Check if GPU is detected
ollama ps

# Force CPU-only mode (if needed)
CUDA_VISIBLE_DEVICES="" ollama serve
```

## Management Commands

### Start/Stop Ollama
```bash
# Start server (background)
ollama serve &

# Stop server
pkill ollama

# Check if running
pgrep ollama
```

### Model Management
```bash
# List installed models
ollama list

# Remove a model
ollama rm qwen2.5:8b

# Update a model
ollama pull qwen2.5:8b
```

### Test Model Directly
```bash
# Interactive chat
ollama run qwen2.5:8b

# Single query
ollama run qwen2.5:8b "What is Pydantic AI?"
```

## Switching Back to Azure

To switch back to Azure AI Foundry:

```bash
# In .env file
LLM_PROVIDER=azure

# Ensure Azure credentials are set
AZURE_AI_FOUNDRY_ENDPOINT=your-endpoint
AZURE_AI_FOUNDRY_API_KEY=your-key
AZURE_DEPLOYMENT_NAME=DeepSeek-V3.2
```

## Troubleshooting

### "Connection refused" Error
```bash
# Check if Ollama is running
pgrep ollama || ollama serve &

# Wait a few seconds for server to start
sleep 5
```

### Model Not Found
```bash
# Verify model is installed
ollama list

# Pull model if missing
ollama pull qwen2.5:8b
```

### Slow Performance
```bash
# Check if GPU is being used
ollama ps  # Look for "GPU" in output

# Reduce context window in .env
LLM_MAX_TOKENS=2048
```

### Out of Memory
```bash
# Use smaller model
LLM_MODEL_NAME=mistral:7b

# Or quantized version
ollama pull qwen2.5:8b-q4
LLM_MODEL_NAME=qwen2.5:8b-q4
```

## Advanced: Custom Models

Create custom Ollama models with specific parameters:

```bash
# Create custom Modelfile
cat > Modelfile <<EOF
FROM qwen2.5:8b

# System prompt
SYSTEM You are a research assistant specialized in academic papers.

# Parameters
PARAMETER temperature 0.4
PARAMETER num_ctx 16384
PARAMETER top_p 0.9
EOF

# Build custom model
ollama create research-assistant -f Modelfile

# Use in .env
LLM_MODEL_NAME=research-assistant
```

## References

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Ollama Model Library](https://ollama.com/library)
- [Qwen2.5 Model Card](https://ollama.com/library/qwen2.5)
- [Pydantic AI Documentation](https://ai.pydantic.dev/)

## Support

For issues specific to:
- **Ollama installation**: See [Ollama GitHub Issues](https://github.com/ollama/ollama/issues)
- **Integration with this project**: Open an issue in this repository
- **Model performance**: Check [Ollama Discord](https://discord.gg/ollama)
