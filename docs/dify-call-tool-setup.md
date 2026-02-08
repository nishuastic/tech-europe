# Interactive Call Hotline Tool - Dify Configuration

## Overview

This tool enables **agent-mediated phone calls** where Dify controls the conversation with CAF (French social services). The user sees the live transcript and can override if needed, but the agent decides what to say.

## Architecture

```
User asks to call CAF
        ↓
Dify triggers call_hotline_interactive
        ↓
Backend dials CAF, connects audio
        ↓
CAF speaks → STT → Translation → Backend
        ↓
Backend calls Dify: "What should I respond?"
        ↓
Dify decides response → Translation → TTS → CAF hears it
        ↓
[Loop continues until call ends]
```

## Tool: call_hotline_interactive

### Purpose
Initiates an interactive phone call where the agent handles the conversation on behalf of the user.

### OpenAPI Specification

```yaml
openapi: 3.1.0
info:
  title: Interactive Call API
  version: 1.0.0
  description: Agent-mediated phone calls to French hotlines

servers:
  - url: https://YOUR_NGROK_URL.ngrok-free.app/api/v1/call

paths:
  /initiate-interactive:
    post:
      operationId: initiateInteractiveCall
      summary: Start an agent-controlled call to a French hotline
      description: |
        Initiates a phone call where the Dify agent controls the conversation.
        The agent will:
        1. Listen to what CAF says (via STT + translation)
        2. Decide how to respond based on context
        3. Speak the response to CAF (via translation + TTS)
        
        The user sees the live transcript and can override if needed.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - target
                - message
              properties:
                target:
                  type: string
                  enum: [caf, prefecture, impots]
                  description: Which French hotline to call
                message:
                  type: string
                  description: User's question or reason for calling
      responses:
        '200':
          description: Call initiated
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    enum: [calling, failed]
                  message:
                    type: string
                  call_action:
                    type: object
                    properties:
                      call_id:
                        type: string
                      target:
                        type: string
                      status:
                        type: string
```

## Dify Configuration Steps

### 1. Import the Tool

1. Go to **Dify Studio** → Your Application → **Tools**
2. Click **Add Tool** → **Custom Tool**
3. Select **Import from OpenAPI**
4. Paste the OpenAPI spec above
5. Replace `YOUR_NGROK_URL` with your actual ngrok URL (e.g., `abc123.ngrok-free.app`)
6. Save the tool

### 2. Update Agent System Prompt

Add this to your agent's system prompt:

```markdown
## Phone Call Capabilities

You can make phone calls to French hotlines on behalf of users. When a user asks you to call CAF, Prefecture, or Impots:

1. Use the `call_hotline_interactive` tool
2. The call will start automatically
3. You will control the conversation - deciding what to say based on:
   - The user's original question
   - What CAF says during the call
   - The conversation context

### When to use this tool:
- User says "call CAF for me"
- User asks "can you talk to the prefecture?"
- User needs real-time phone assistance
- User wants you to handle the bureaucracy

### Example:
User: "Can you call CAF to check on my APL application?"
→ call_hotline_interactive(target="caf", message="Check APL application status")

The user will see the live transcript and can override your responses if needed.
```

### 3. Agent Response Behavior

During the call, the backend will send prompts like:

```
You are on a live phone call with CAF (French social services) on behalf of a user.

USER'S ORIGINAL QUESTION: Check APL application status

CALL TRANSCRIPT SO FAR:
CAF: Bonjour, vous êtes en ligne avec la CAF...
Me: Bonjour, je voudrais vérifier le statut de ma demande d'APL
CAF: D'accord, pouvez-vous me donner votre numéro d'allocataire?

CAF JUST SAID: "Sure, can you give me your beneficiary number?"

Based on this context, what should you say next to CAF?
```

The agent should respond with just the text to say, e.g.:
```
I don't have that number handy. Can you look me up by my name and date of birth instead?
```

## Testing

### Test Locally

1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Start ngrok: `ngrok http 8000`
3. Update `BACKEND_PUBLIC_URL` in `.env` with ngrok URL
4. Start frontend: `cd bureaucracy-buddy && npm run dev`
5. Ask the agent: "Call CAF for me about my APL"

### Expected Behavior

1. Agent response includes `call_action` with `call_id`
2. Frontend auto-opens LiveCallUI
3. Call dials (your test phone should ring)
4. CAF speaks → transcript appears in UI
5. Agent thinking indicator shows
6. Agent's response appears and is spoken to CAF
7. Repeat until call ends

## Troubleshooting

### "Agent not responding during call"
- Check backend logs for Dify API errors
- Verify `DIFY_API_KEY` is set correctly
- Ensure Dify conversation isn't hitting rate limits

### "Call not dialing"
- Verify ngrok is running and URL is correct
- Check Twilio credentials in `.env`
- Verify the target phone number is set

### "No audio from CAF"
- Check Gradium API key
- Verify Twilio Media Streams is connecting
- Check WebSocket connections in browser devtools
