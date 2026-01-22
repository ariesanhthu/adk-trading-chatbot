import os
import asyncio
from agents import root_agent

# Force Ollama (though root_agent is already initialized, we hope it picked up env vars or defaults)
# Ideally we should see "Using Ollama model" in the output during import.

async def main():
    print("Testing root_agent...")
    
    print("\nAttempting generation via agent...")
    try:
        response = await root_agent.run("Xin chào, bạn có khỏe không?")
        print("\nResponse:")
        print(response)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
