from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey, Index, UniqueConstraint, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()


class Role(Base):
    """角色配置表"""
    __tablename__ = "roles"
    __table_args__ = {
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(100), nullable=False, unique=True)
    system_prompt = Column(Text, nullable=False)
    system_prompt_friend = Column(Text, nullable=True)
    system_prompt_partner = Column(Text, nullable=True)
    system_prompt_lover = Column(Text, nullable=True)
    scenario = Column(Text, nullable=True)
    greeting_message = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Role(id={self.id}, role_name={self.role_name})>"


class RoleRelationshipPrompt(Base):
    """角色关系等级提示词表"""
    __tablename__ = "role_relationship_prompts"
    __table_args__ = (
        UniqueConstraint("role_id", "relationship", name="uk_role_relationship_prompt"),
        Index("idx_role_relationship_prompt", "role_id", "relationship", "is_active"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    relationship = Column(Integer, nullable=False, default=1)
    prompt_text = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<RoleRelationshipPrompt(role_id={self.role_id}, "
            f"relationship={self.relationship}, is_active={self.is_active})>"
        )


class RoleImage(Base):
    """角色图片资源表"""
    __tablename__ = "role_images"
    __table_args__ = (
        Index("idx_role_image_order", "role_id", "image_type", "sort_order"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    image_url = Column(String(500), nullable=False)
    image_type = Column(String(50), nullable=False, default="avatar")
    stage_key = Column(String(50), nullable=True)
    trigger_type = Column(String(50), nullable=False, default="manual")
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    meta_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<RoleImage(id={self.id}, role_id={self.role_id}, "
            f"type={self.image_type}, stage={self.stage_key})>"
        )


class UserRole(Base):
    """用户-角色关系表"""
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    relationship = Column(Integer, nullable=False, default=3)
    is_current = Column(Boolean, default=False)
    first_interaction_at = Column(DateTime, nullable=True)
    last_interaction_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uk_user_role"),
        Index("idx_user_current", "user_id", "is_current"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    def __repr__(self):
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id}, is_current={self.is_current})>"


class MessageType(str, enum.Enum):
    """消息类型枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    ASSISTANT_IMAGE = "assistant_image"


class ChatHistory(Base):
    """聊天记录表"""
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    message_type = Column(Enum(MessageType), nullable=False)
    content = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    emotion_data = Column(JSON, nullable=True)
    decision_data = Column(JSON, nullable=True)
    meta_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_user_role_time", "user_id", "role_id", "created_at"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    def __repr__(self):
        return f"<ChatHistory(user_id={self.user_id}, role_id={self.role_id}, type={self.message_type})>"
