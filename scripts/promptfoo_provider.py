import os
import sys
import json
import requests

def call_api(prompt, options, context):
    """
    Promptfoo Python Provider for ADK Trading Chatbot.
    """
    url = "http://localhost:8002/api/v1/chat"
    
    # Construct the payload matching app/schemas/chat.py:ChatRequest
    payload = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "meta": {
            "user_id": "test_user",
            "session_id": "test_session"
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        
        # Extract reply and ui_effects
        reply = data.get("reply", "")
        ui_effects = data.get("ui_effects", [])
        
        # Return structured output for Promptfoo
        return {
            "output": reply,
            "metadata": {
                "ui_effects": ui_effects,
                "raw_response": data
            }
        }
    except Exception as e:
        return {
            "error": f"API Call Failed: {str(e)}"
        }

if __name__ == "__main__":
    # Test execution
    print(json.dumps(call_api("Giá VCB hôm nay?", {}, {}), indent=2))
