"""
AI service for AcadSync Academic Assistant using Google's Gemini API.
Handles Gemini client configuration, system prompt assembly with pre-calculated
academic snapshots, conversation history formatting, and graceful error handling.
"""

import logging
import os
import google.generativeai as genai
from flask import current_app
from app.services.context_builder import build_user_context

logger = logging.getLogger(__name__)

# Track configuration state
_is_configured = False


def configure_gemini():
    """
    Configures the google-generativeai client using GEMINI_API_KEY from Flask config or environment.
    Can be called during app creation or lazily before the first request.
    """
    global _is_configured
    api_key = None

    if current_app:
        api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY')

    if not api_key or not api_key.strip():
        logger.warning("GEMINI_API_KEY is not set. AI Academic Assistant calls will fail.")
        return False

    try:
        genai.configure(api_key=api_key.strip())
        _is_configured = True
        return True
    except Exception as e:
        logger.error(f"Failed to configure Gemini client: {e}")
        return False


def sanitize_gemini_history(conversation_history, max_turns: int = 10):
    """
    Sanitizes conversation history into Gemini's expected [{'role': 'user'|'model', 'parts': [...]}] format.
    Gemini requires:
    1. History must start with a 'user' message.
    2. Roles must alternate between 'user' and 'model'.
    """
    if not conversation_history:
        return []

    # Take the last max_turns messages
    recent_messages = list(conversation_history)[-max_turns:]
    gemini_history = []

    for msg in recent_messages:
        role = getattr(msg, 'role', None) or (msg.get('role') if isinstance(msg, dict) else None)
        content = getattr(msg, 'content', None) or (msg.get('content') if isinstance(msg, dict) else None)

        if not content or not str(content).strip():
            continue

        target_role = 'user' if role == 'user' else 'model'

        # Ensure history starts with 'user'
        if not gemini_history and target_role != 'user':
            continue

        # Prevent duplicate consecutive roles
        if gemini_history and gemini_history[-1]['role'] == target_role:
            # Combine content with previous message of same role
            gemini_history[-1]['parts'][0] += f"\n\n{content.strip()}"
        else:
            gemini_history.append({'role': target_role, 'parts': [content.strip()]})

    # If the last message in history is a 'user' message, remove it because user_message will be sent next
    if gemini_history and gemini_history[-1]['role'] == 'user':
        gemini_history.pop()

    return gemini_history


def get_ai_response(user, conversation_history, user_message: str) -> str:
    """
    Generates an AI response from Gemini based on the user's factual academic snapshot.

    Args:
        user: The authenticated User model instance
        conversation_history: List of AIMessage instances or history dicts
        user_message: The latest text prompt from the user

    Returns:
        str: Assistant's markdown-formatted reply, or a friendly error message.
    """
    # 1. Ensure Gemini is configured
    if not _is_configured:
        if not configure_gemini():
            return (
                "The AI Academic Assistant is currently unavailable because the **GEMINI_API_KEY** "
                "is not configured on this server. Please add your Gemini API key to `.env` to enable this feature."
            )

    # 2. Build the factual academic context (Pre-calculated by Flask backend)
    try:
        user_academic_context = build_user_context(user)
    except Exception as e:
        logger.error(f"Error building academic context for user {user.id}: {e}")
        user_academic_context = "Could not retrieve user academic snapshot due to an internal error."

    # 3. Formulate strict system instructions
    system_instruction = (
        "You are AcadSync's Academic Assistant. You help university students understand their "
        "academic standing across both VIT and IITM universities, prioritize tasks, and prepare for exams.\n\n"
        "CRITICAL BEHAVIORAL RULES (MANDATORY):\n"
        "1. NEVER perform, calculate, or estimate a grade or score yourself. You must NEVER do grade math.\n"
        "2. ONLY cite the exact pre-calculated scores and grades supplied in the ACADEMIC SNAPSHOT below.\n"
        "3. If the student asks you to calculate what score they need on upcoming tests, simulate grades, "
        "or evaluate what-if scenarios, politely decline and explicitly instruct them to use AcadSync's "
        "dedicated **Grade Calculator** feature on the subject page.\n"
        "4. If a course status shows 'Score not yet calculable', inform the user which specific marks are missing as stated in the snapshot.\n"
        "5. Cross-reference both VIT and IITM subjects when asked about workload, priorities, or what needs immediate attention.\n"
        "6. Emphasize overdue tasks and impending deadlines in your recommendations.\n"
        "7. Keep your tone encouraging, professional, concise, and structured with clean Markdown.\n\n"
        "=== ACADSYNC PRE-CALCULATED ACADEMIC SNAPSHOT ===\n"
        f"{user_academic_context}\n"
        "================================================"
    )

       # 4. Invoke Gemini model (single call, no fallback loop)
    sanitized_history = sanitize_gemini_history(conversation_history)

    try:
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_instruction
        )

        if sanitized_history:
            chat = model.start_chat(history=sanitized_history)
            response = chat.send_message(user_message.strip())
        else:
            response = model.generate_content(user_message.strip())

        if response and response.text:
            return response.text.strip()
        return "I received an empty response from the AI service. Please try rephrasing your question."

    except Exception as e:
        error_str = str(e).lower()
        logger.error(f"Gemini API error for user {user.id}: {e}")
        if "api_key" in error_str or "permission" in error_str or "unauthenticated" in error_str:
            return "Authentication with the Gemini API failed. Please verify that your `GEMINI_API_KEY` is valid."
        elif "quota" in error_str or "rate limit" in error_str or "resource_exhausted" in error_str:
            return "The AI assistant has reached its daily quota. Please try again tomorrow."
        else:
            return "I apologize, but I encountered an error communicating with the AI service. Please try again in a moment."