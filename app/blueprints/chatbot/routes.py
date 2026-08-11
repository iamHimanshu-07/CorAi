from flask import Blueprint, request, jsonify, session, current_app
from openai import OpenAI

# Optional RAG engine. Imported lazily so the rest of the app keeps working
# even if the RAG deps aren't installed.
try:
    from rag_engine import get_bot_response_safe as _rag_reply, is_configured as _rag_ready
    _RAG_AVAILABLE = True
except Exception:  # noqa: BLE001
    _RAG_AVAILABLE = False
    _rag_reply = None
    _rag_ready = None

bp = Blueprint('chatbot', __name__)


@bp.route('/chat', methods=['POST'])
def chat():
    """Handle a user message and forward it to the configured chatbot backend.

    Routing order:
      1. If the RAG engine is configured (Google API key set and deps present)
         and the question is *not* pure OpenAI-specific history, use RAG.
      2. Otherwise, fall back to the OpenAI Chat Completions API (legacy path,
         kept for backwards compatibility with existing deployments).

    The frontend in ``app/templates/base.html`` POSTs ``{"message": "..."}``
    and reads ``{"reply": "..."}``.
    """
    data = request.get_json(silent=True) or {}
    user_msg = data.get('message')
    if not user_msg:
        return jsonify({"error": "Message is required"}), 400

    # 1. Try the RAG engine (Gemini + local FAISS over the CorAi knowledge base).
    if _RAG_AVAILABLE and _rag_ready and _rag_ready():
        reply = _rag_reply(user_msg)
        return jsonify({"reply": reply})

    # 2. Fall back to OpenAI.
    history = session.get('chat_history', [])
    history.append({"role": "user", "content": user_msg})

    try:
        api_key = current_app.config.get('LLM_API_KEY')
        if not api_key:
            # If the RAG engine isn't ready either, surface a single clear
            # error so the frontend widget can show it.
            if _RAG_AVAILABLE:
                reply = _rag_reply(user_msg) if _rag_reply else "Chatbot is not configured."
                return jsonify({"reply": reply})
            return jsonify({"error": "OpenAI API Key (LLM_API_KEY) is not set in application configuration"}), 500

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=current_app.config.get('LLM_MODEL', 'gpt-3.5-turbo'),
            messages=history
        )
        assistant_msg = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": assistant_msg})
        session['chat_history'] = history
        return jsonify({"reply": assistant_msg})
    except Exception as e:
        current_app.logger.exception("Chatbot error")
        return jsonify({"error": str(e)}), 500
