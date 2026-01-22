import sys
import json
import requests
import os

def call_api(prompt, options, context):
    """
    Sends the prompt to the ADK Chatbot API and returns a structured JSON response
    compatible with Promptfoo evaluation.
    """
    # Configuration
    API_URL = os.getenv("ADK_API_URL", "http://localhost:8002/api/v1/chat")
    
    payload = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "meta": {
            "user_id": "promptfoo_user",
            "session_id": "eval_session"
        }
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        # Extract fields
        # Assuming standard ADK response structure: 
        # { "reply": "text...", "ui_effects": [{"type": "tool_call", ...}] }
        final_response = data.get("reply", "")
        # ui_effects acts as our tool calls or side effects container
        ui_effects = data.get("ui_effects", [])
        
        # Transform ui_effects to tool_calls if necessary or just pass them through
        # The user requested specific "tool_calls" structure in the output JSON.
        # We map ui_effects to tool_calls for clarity in testing.
        tool_calls = []
        for effect in ui_effects:
            # Clean up effect to ensure it looks like a tool call {name, arguments}
            # Adjust this logic based on actual ui_effects structure key names
            if isinstance(effect, dict):
                 # Try to normalize or just keep as is
                 tool_calls.append(effect)

        # Construct the final structured output
        result = {
            "output": {
                "final_response": final_response,
                "tool_calls": tool_calls
            }
        }
        
        return result

    except requests.exceptions.RequestException as e:
        # Handle connection errors (e.g., server down)
        return {
            "error": f"API Request Failed: {str(e)}",
            "output": {
                "final_response": "ERROR: Could not contact agent.",
                "tool_calls": []
            }
        }
    except Exception as e:
        # Handle other errors
        return {
            "error": f"Internal Wrapper Error: {str(e)}",
            "output": {
                "final_response": "ERROR: Wrapper malfunction.",
                "tool_calls": []
            }
        }

if __name__ == "__main__":
    # Promptfoo passes the prompt as the first argument
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
    else:
        prompt = "Hello"

    # Get structured result
    output = call_api(prompt, {}, {})
    
    # Print JSON to stdout for Promptfoo to capture
    print(json.dumps(output))
