from datetime import datetime
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.ai_conversation import AIConversation, AIMessage
from app.services.ai_service import get_ai_response

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')


@ai_bp.route('/chat', methods=['GET'])
@login_required
def chat():
    """
    Main chat interface router.
    If the user has an existing conversation, redirect to the most recent one.
    Otherwise, create a new conversation and redirect to it.
    """
    recent_conv = (
        AIConversation.query.filter_by(user_id=current_user.id)
        .order_by(AIConversation.updated_at.desc(), AIConversation.created_at.desc())
        .first()
    )

    if not recent_conv:
        recent_conv = AIConversation(
            user_id=current_user.id,
            title='New Conversation'
        )
        db.session.add(recent_conv)
        db.session.commit()

    return redirect(url_for('ai.chat_conversation', conversation_id=recent_conv.id))


@ai_bp.route('/chat/<int:conversation_id>', methods=['GET'])
@login_required
def chat_conversation(conversation_id):
    """
    Load a specific conversation and all its messages.
    Also provides the full list of the user's past conversations for the sidebar.
    """
    conversation = AIConversation.query.get_or_404(conversation_id)

    if not conversation.belongs_to_user(current_user.id):
        abort(403)

    user_conversations = (
        AIConversation.query.filter_by(user_id=current_user.id)
        .order_by(AIConversation.updated_at.desc(), AIConversation.created_at.desc())
        .all()
    )

    return render_template(
        'ai/chat.html',
        active_conversation=conversation,
        conversations=user_conversations,
        messages=conversation.messages
    )


@ai_bp.route('/chat/new', methods=['POST'])
@login_required
def new_conversation():
    """
    Create a new empty AIConversation and redirect to it.
    """
    new_conv = AIConversation(
        user_id=current_user.id,
        title='New Conversation'
    )
    db.session.add(new_conv)
    db.session.commit()

    return redirect(url_for('ai.chat_conversation', conversation_id=new_conv.id))


@ai_bp.route('/chat/<int:conversation_id>/send', methods=['POST'])
@login_required
def send_message(conversation_id):
    """
    Process incoming chat messages.
    Supports both JSON payloads (AJAX) and traditional form posts.
    """
    conversation = AIConversation.query.get_or_404(conversation_id)

    if not conversation.belongs_to_user(current_user.id):
        abort(403)

    # Extract user input
    if request.is_json:
        payload = request.get_json() or {}
        user_content = payload.get('message', '').strip()
    else:
        user_content = request.form.get('message', '').strip()

    if not user_content:
        if request.is_json:
            return jsonify({'error': 'Message cannot be empty.'}), 400
        flash('Message cannot be empty.', 'error')
        return redirect(url_for('ai.chat_conversation', conversation_id=conversation.id))

    # Retrieve existing conversation messages before adding the new one (for context)
    existing_messages = list(conversation.messages)

    # Save user message
    user_msg = AIMessage(
        conversation_id=conversation.id,
        role='user',
        content=user_content
    )
    db.session.add(user_msg)

    # Auto-generate title from the first message if this conversation still has default title
    if conversation.title in {'New Conversation', 'New Chat', ''} or not existing_messages:
        first_line = user_content.split('\n')[0].strip()
        auto_title = first_line[:38] + ('...' if len(first_line) > 38 else '')
        conversation.title = auto_title

    conversation.updated_at = datetime.utcnow()

    # Call AI service with academic snapshot + history
    ai_reply = get_ai_response(
        user=current_user,
        conversation_history=existing_messages,
        user_message=user_content
    )

    # Save assistant response
    assistant_msg = AIMessage(
        conversation_id=conversation.id,
        role='assistant',
        content=ai_reply
    )
    db.session.add(assistant_msg)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': 'Failed to save messages to database.'}), 500
        flash('Failed to save message. Please try again.', 'error')
        return redirect(url_for('ai.chat_conversation', conversation_id=conversation.id))

    # Return response
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'status': 'success',
            'conversation_id': conversation.id,
            'conversation_title': conversation.title,
            'user_message': {
                'id': user_msg.id,
                'role': 'user',
                'content': user_msg.content,
                'created_at': user_msg.created_at.strftime('%I:%M %p')
            },
            'assistant_message': {
                'id': assistant_msg.id,
                'role': 'assistant',
                'content': assistant_msg.content,
                'created_at': assistant_msg.created_at.strftime('%I:%M %p')
            }
        })

    return redirect(url_for('ai.chat_conversation', conversation_id=conversation.id))


@ai_bp.route('/conversations', methods=['GET'])
@login_required
def list_conversations():
    """
    Returns JSON list of current user's past conversations for AJAX history updating.
    """
    user_conversations = (
        AIConversation.query.filter_by(user_id=current_user.id)
        .order_by(AIConversation.updated_at.desc(), AIConversation.created_at.desc())
        .all()
    )

    return jsonify([
        {
            'id': c.id,
            'title': c.title,
            'created_at': c.created_at.strftime('%b %d, %Y')
        }
        for c in user_conversations
    ])


@ai_bp.route('/conversation/<int:conversation_id>/delete', methods=['POST'])
@login_required
def delete_conversation(conversation_id):
    """
    Deletes an AI conversation and its messages.
    """
    conversation = AIConversation.query.get_or_404(conversation_id)

    if not conversation.belongs_to_user(current_user.id):
        abort(403)

    try:
        db.session.delete(conversation)
        db.session.commit()
        flash('Conversation deleted.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to delete conversation.', 'error')

    if request.is_json:
        return jsonify({'status': 'success', 'deleted_id': conversation_id})

    return redirect(url_for('ai.chat'))
