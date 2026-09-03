from datetime import datetime
from app.extensions import db


class AIConversation(db.Model):
    """
    AI Conversation session model.
    A conversation belongs to a user and has multiple messages ordered by creation time.
    """
    __tablename__ = 'ai_conversations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    title = db.Column(db.String(255), nullable=False, default='New Conversation', server_default='New Conversation')
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        server_default=db.func.now(),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=db.func.now(),
        nullable=False
    )

    # Relationship to AIMessage
    messages = db.relationship(
        'AIMessage',
        backref='conversation',
        lazy=True,
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='AIMessage.created_at.asc()'
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<AIConversation {self.id}: {self.title}>'

    def belongs_to_user(self, user_id):
        """
        Check if conversation belongs to specified user.
        """
        return self.user_id == user_id


class AIMessage(db.Model):
    """
    Individual message in an AI conversation.
    role: 'user' or 'assistant'
    """
    __tablename__ = 'ai_messages'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey('ai_conversations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        server_default=db.func.now(),
        nullable=False
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<AIMessage {self.id} ({self.role}) in Conv {self.conversation_id}>'
