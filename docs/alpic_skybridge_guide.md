# Alpic Skybridge: ChatGPT App Integration

This guide explains how to expose your local **AdminHero** backend to ChatGPT, allowing you to use the official ChatGPT interface (web or mobile) as a frontend for your French Bureaucracy Copilot.

## Prerequisites

1.  **ChatGPT Plus** account (required for Custom GPTs).
2.  **ngrok** installed (to expose localhost to the internet).
    ```bash
    brew install ngrok/ngrok/ngrok
    ```

---

## Step 1: Expose Local Backend

Start your backend server if not running:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

In a new terminal, expose port 8000:
```bash
ngrok http 8000
```
Copy the HTTPS URL (e.g., `https://a1b2-c3d4.ngrok-free.app`).

---

## Step 2: Create Custom GPT

1.  Go to [ChatGPT](https://chat.openai.com/).
2.  Click **Explore** -> **Create a GPT**.
3.  **Name**: AdminHero
4.  **Description**: Your French Bureaucracy Copilot.
5.  **Instructions**:
    ```
    You are AdminHero, an expert in French bureaucracy.
    When a user asks a question about French administration (visas, taxes, housing, etc.), use the `process_text` action to get an expert explanation and an email draft.
    
    Always present the 'explanation' clearly.
    If an 'email_draft' is provided, display it in a code block or clean format for the user to copy.
    
    If the user asks to "speak" the answer or "read it aloud", use the `synthesize_speech` action to generate an audio link.
    ```

---

## Step 3: Configure Actions

1.  Click **Create new action**.
2.  **Authentication**: None.
3.  **Schema**: Copy the JSON below. **IMPORTANT**: Replace `YOUR_NGROK_URL` with your actual ngrok URL (e.g., `https://a1b2.ngrok-free.app`).

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "AdminHero API",
    "description": "API for French Bureaucracy assistance.",
    "version": "1.0.0"
  },
  "servers": [
    {
      "url": "YOUR_NGROK_URL"
    }
  ],
  "paths": {
    "/api/v1/agent/chat": {
      "post": {
        "description": "Get expert explanation and email draft for a query.",
        "operationId": "process_text",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "message": {
                    "type": "string",
                    "description": "The user's question about French administration."
                  },
                  "conversation_id": {
                    "type": "string",
                    "nullable": true,
                    "description": "Optional ID to continue a conversation."
                  }
                },
                "required": ["message"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successful response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "transcript": { "type": "string" },
                    "explanation": { "type": "string" },
                    "email_draft": {
                      "type": "object",
                      "properties": {
                        "subject": { "type": "string" },
                        "body": { "type": "string" },
                        "recipient": { "type": "string" }
                      }
                    },
                    "conversation_id": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/agent/tts": {
      "post": {
        "description": "Convert text to speech (WAV audio).",
        "operationId": "synthesize_speech",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "text": {
                    "type": "string",
                    "description": "Text to speak."
                  },
                  "voice": {
                    "type": "string",
                    "enum": ["english_female", "english_male", "french_female", "french_male"],
                    "default": "english_female"
                  }
                },
                "required": ["text"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Audio file (WAV)",
            "content": {
              "audio/wav": {
                "schema": {
                  "type": "string",
                  "format": "binary"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/call/initiate": {
      "post": {
        "description": "Call a French hotline (CAF, Prefecture, etc.) and speak the user's message in French.",
        "operationId": "initiate_call",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "message": {
                    "type": "string",
                    "description": "The user's message in English to be spoken to the hotline."
                  },
                  "target": {
                    "type": "string",
                    "enum": ["caf", "prefecture", "impots"],
                    "description": "The hotline to call."
                  }
                },
                "required": ["message", "target"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Call initiated",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "call_id": { "type": "string" },
                    "status": { "type": "string" },
                    "french_message": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/call/status/{call_id}": {
      "get": {
        "description": "Check the status of an ongoing call and get the translated response.",
        "operationId": "check_call_status",
        "parameters": [
          {
            "name": "call_id",
            "in": "path",
            "required": true,
            "schema": { "type": "string" }
          }
        ],
        "responses": {
          "200": {
            "description": "Call status",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "status": { "type": "string" },
                    "french_response": { "type": "string" },
                    "english_response": { "type": "string" },
                    "error": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## Step 4: Test

1.  In the Preview pane, ask: "How do I renew my talent passport?"
2.  Allow the action to run.
3.  You should see the explanation from your backend!
4.  Ask: "Can you read that to me?" -> It should generate a download link for the audio.

## Deployment Notes

For a permanent "Skybridge", deploy your backend to a public cloud (Railway/Render) to get a stable HTTPS URL, then update the Action Schema `servers` URL.
