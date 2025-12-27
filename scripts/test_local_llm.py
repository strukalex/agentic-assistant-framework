#!/usr/bin/env python3
"""Test script for local LLM setup.

Run this script to verify that your local Ollama setup is working correctly
and can be used by the ResearcherAgent.

Usage:
    python scripts/test_local_llm.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from paias.core.llm import get_azure_model
from paias.core.config import settings


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_model_connection():
    """Test that we can connect to the configured LLM provider."""
    print("=" * 80)
    print("Testing LLM Connection")
    print("=" * 80)

    # Show current configuration
    print(f"\n📋 Current Configuration:")
    print(f"   Provider: {settings.llm_provider}")

    if settings.llm_provider.lower() == "local":
        print(f"   Model: {settings.llm_model_name}")
        print(f"   Base URL: {settings.llm_base_url}")
    else:
        print(f"   Provider: Azure AI Foundry")

    print(f"   Temperature: {settings.llm_temperature}")
    print(f"   Max Tokens: {settings.llm_max_tokens or 'default'}")

    # Test model creation
    print(f"\n🔧 Creating model instance...")
    try:
        model = get_azure_model()
        print(f"✅ Model created successfully")
        print(f"   Type: {type(model).__name__}")

        # Try a simple inference
        print(f"\n💬 Testing inference with simple query...")
        from pydantic_ai import Agent

        test_agent = Agent(model=model)
        result = await test_agent.run("Say 'Hello from Ollama!' if you can hear me.")

        # Extract response
        response = getattr(result, "data", None) or getattr(result, "output", None)
        print(f"✅ Inference successful!")
        print(f"\n📝 Model Response:")
        print(f"   {response}")

        print(f"\n{'=' * 80}")
        print(f"✅ ALL TESTS PASSED")
        print(f"{'=' * 80}")
        print(f"\nYour local LLM is ready to use!")
        print(f"The ResearcherAgent will now use: {settings.llm_model_name}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"\n{'=' * 80}")
        print(f"❌ TEST FAILED")
        print(f"{'=' * 80}")
        print(f"\nTroubleshooting:")

        if settings.llm_provider.lower() == "local":
            print(f"1. Check if Ollama is running:")
            print(f"   pgrep ollama || ollama serve &")
            print(f"\n2. Check if model is installed:")
            print(f"   ollama list")
            print(f"\n3. Pull the model if missing:")
            print(f"   ollama pull {settings.llm_model_name}")
            print(f"\n4. Test model directly:")
            print(f"   ollama run {settings.llm_model_name} 'Hello!'")
        else:
            print(f"1. Check Azure credentials in .env:")
            print(f"   AZURE_AI_FOUNDRY_ENDPOINT")
            print(f"   AZURE_AI_FOUNDRY_API_KEY")
            print(f"   AZURE_DEPLOYMENT_NAME")

        return False


async def main():
    """Main test runner."""
    success = await test_model_connection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
