"""
Dify API Service

Handles communication with the Dify API for RAG-powered reasoning.
"""

import httpx
import logging
import json
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


async def call_dify_chat(
    query: str,
    inputs: dict = None,
    conversation_id: Optional[str] = None,
    user_id: str = "hackathon-user",
) -> dict:
    """
    Call Dify chat-messages API to get explanation and email draft.

    Args:
        query: The transcribed user query
        inputs: Optional dictionary of context variables for the Dify workflow
        conversation_id: Optional conversation ID for context continuity
        user_id: User identifier

    Returns:
        Dict with Dify response containing explanation and action
    """
    if not settings.dify_api_key:
        raise ValueError("DIFY_API_KEY is not configured")

    url = f"{settings.dify_api_url}/chat-messages"

    headers = {
        "Authorization": f"Bearer {settings.dify_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "inputs": inputs or {},
        "query": query,
        "response_mode": "streaming",  # Agent apps require streaming mode
        "user": user_id,
    }

    if conversation_id and conversation_id.strip():
        payload["conversation_id"] = conversation_id

    logger.info(
        f"Calling Dify (streaming): query='{query[:50]}...', conv_id={conversation_id}"
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        # First attempt
        should_retry = False

        async with client.stream(
            "POST", url, json=payload, headers=headers
        ) as response:
            if response.status_code == 400 and conversation_id:
                should_retry = True
                logger.warning(
                    f"Dify 400 error with conv_id {conversation_id}, retrying without it..."
                )
            else:
                return await _process_stream(response)

        # Retry with new request if needed
        if should_retry:
            if "conversation_id" in payload:
                del payload["conversation_id"]

            async with client.stream(
                "POST", url, json=payload, headers=headers
            ) as new_response:
                return await _process_stream(new_response)


async def _process_stream(response) -> dict:
    """Process Dify SSE stream and accumulate answer."""

    if response.status_code != 200:
        error_text = await response.aread()
        raise ValueError(
            f"Dify API error {response.status_code}: {error_text.decode()}"
        )

    full_answer = ""
    conversation_id = None

    async for line in response.aiter_lines():
        if not line or not line.startswith("data: "):
            continue

        data_str = line[6:]  # Skip "data: "
        try:
            data = json.loads(data_str)

            event = data.get("event")

            if event in ["message", "agent_message"]:
                full_answer += data.get("answer", "")
            elif event == "message_end":
                conversation_id = data.get("conversation_id")
                # Metadata usage etc can be captured here if needed

        except json.JSONDecodeError:
            continue

    # Return structured dict compatible with existing code
    return {
        "answer": full_answer,
        "conversation_id": conversation_id,
        "explanation": full_answer,  # Fallback
        "raw_answer": full_answer,
    }


def parse_dify_response(dify_response: dict) -> dict:
    """
    Parse the Dify response to extract explanation, email draft, and call action.

    The Dify workflow should be configured to output structured JSON.
    This function handles both raw text and structured responses.

    When Dify uses the call_hotline tool, it should include:
    - call_action: { call_id, target, status }

    Args:
        dify_response: Raw response from Dify API

    Returns:
        Structured dict with explanation, email_draft, and optionally call_action
    """
    # Extract the answer from Dify response
    answer = dify_response.get("answer", "")
    conversation_id = dify_response.get("conversation_id", "")

    # Also check for metadata that might contain tool outputs
    metadata = dify_response.get("metadata", {})
    tool_outputs = metadata.get("tool_outputs", [])

    # Initialize result structure
    result = {
        "explanation": answer,
        "email_draft": {},
        "action": None,
        "conversation_id": conversation_id,
    }

    # Check tool outputs for details
    for output in tool_outputs:
        if isinstance(output, dict):
            if "call_action" in output:
                result["action"] = {"type": "call", **output["call_action"]}
                break
            if "ask_user" in output:
                result["action"] = {"type": "ask_user", **output["ask_user"]}
                break

    # Try to parse as JSON if Dify returns structured output in text
    try:
        import json

        # Attempt to find JSON in the answer
        if "{" in answer and "}" in answer:
            start = answer.find("{")
            end = answer.rfind("}") + 1
            json_str = answer[start:end]
            parsed = json.loads(json_str)

            result["explanation"] = parsed.get("explanation", answer)
            result["email_draft"] = parsed.get("email_draft", {})

            # Extract actions from parsed JSON
            if "action" in parsed:
                # Direct action field
                result["action"] = parsed["action"]
            elif "call_action" in parsed:
                result["action"] = {"type": "call", **parsed["call_action"]}
            elif "ask_user" in parsed:
                result["action"] = {"type": "ask_user", **parsed["ask_user"]}

            # If we found JSON, update everything but keep conversation_id
            return result

    except (json.JSONDecodeError, ValueError):
        pass

    return result


async def translate_text(
    text: str, source_lang: str = "en", target_lang: str = "fr"
) -> str:
    """
    Translate text between languages using OpenAI.

    Args:
        text: Text to translate
        source_lang: Source language code (en, fr)
        target_lang: Target language code (en, fr)

    Returns:
        Translated text
    """
    import openai

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    lang_names = {"en": "English", "fr": "French", "de": "German", "es": "Spanish"}
    target = lang_names.get(target_lang, target_lang)

    if source_lang == "auto":
        system_prompt = f"You are a translator. Translate the following text to {target}. If the text is already in {target}, return it exactly as is. Only output the translation, nothing else."
    else:
        source = lang_names.get(source_lang, source_lang)
        system_prompt = f"You are a translator. Translate the following text from {source} to {target}. Only output the translation, nothing else."

    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {"role": "user", "content": text},
        ],
        temperature=0.3,
        max_tokens=1000,
    )

    return response.choices[0].message.content.strip()
