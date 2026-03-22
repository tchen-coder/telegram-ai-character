from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, JSON, ForeignKey, Index, UniqueConstraint, Enum
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


class RoleRelationshipConfig(Base):
    """角色关系系统配置表"""
    __tablename__ = "role_relationship_configs"
    __table_args__ = (
        UniqueConstraint("role_id", name="uk_role_relationship_config"),
        Index("idx_role_relationship_config", "role_id"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    initial_rv = Column(Integer, nullable=False, default=15)
    update_frequency = Column(Integer, nullable=False, default=1)
    max_negative_delta = Column(Integer, nullable=False, default=3)
    max_positive_delta = Column(Integer, nullable=False, default=15)
    recent_window_size = Column(Integer, nullable=False, default=12)
    stage_names = Column(JSON, nullable=True)
    stage_floor_rv = Column(JSON, nullable=True)
    stage_thresholds = Column(JSON, nullable=True)
    paid_boost_enabled = Column(Boolean, default=False)
    meta_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<RoleRelationshipConfig(role_id={self.role_id})>"


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
    relationship = Column(Integer, nullable=False, default=1)
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


class UserRoleRelationshipState(Base):
    """用户-角色关系状态表"""
    __tablename__ = "user_role_relationship_states"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uk_user_role_relationship_state"),
        Index("idx_user_role_relationship_state", "user_id", "role_id", "current_stage"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    current_rv = Column(Integer, nullable=False, default=15)
    current_stage = Column(Integer, nullable=False, default=1)
    max_unlocked_stage = Column(Integer, nullable=False, default=1)
    last_rv = Column(Integer, nullable=False, default=15)
    last_delta = Column(Integer, nullable=False, default=0)
    last_update_at_turn = Column(Integer, nullable=False, default=0)
    turn_count = Column(Integer, nullable=False, default=0)
    update_frequency = Column(Integer, nullable=False, default=1)
    pending_delta_accumulator = Column(Integer, nullable=False, default=0)
    paid_boost_rv = Column(Integer, nullable=False, default=0)
    paid_boost_applied = Column(Boolean, default=False)
    paid_boost_source = Column(String(50), nullable=True)
    emotion_summary_text = Column(Text, nullable=True)
    emotion_summary_updated_turn = Column(Integer, nullable=False, default=0)
    emotion_adjustment_factor = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<UserRoleRelationshipState(user_id={self.user_id}, role_id={self.role_id}, "
            f"stage={self.current_stage}, rv={self.current_rv})>"
        )


class UserRoleRelationshipEvent(Base):
    """用户-角色关系事件日志表"""
    __tablename__ = "user_role_relationship_events"
    __table_args__ = (
        Index("idx_user_role_relationship_event", "user_id", "role_id", "turn_index"),
        Index("idx_relationship_event_message", "trigger_message_id"),
        {
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    trigger_message_id = Column(Integer, ForeignKey("chat_history.id"), nullable=True)
    turn_index = Column(Integer, nullable=False, default=0)
    triggered_update = Column(Boolean, default=False)
    delta = Column(Integer, nullable=False, default=0)
    pending_before = Column(Integer, nullable=False, default=0)
    applied_delta = Column(Integer, nullable=False, default=0)
    rv_before = Column(Integer, nullable=False, default=15)
    rv_after = Column(Integer, nullable=False, default=15)
    stage_before = Column(Integer, nullable=False, default=1)
    stage_after = Column(Integer, nullable=False, default=1)
    scoring_source = Column(String(50), nullable=True)
    reason_text = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<UserRoleRelationshipEvent(user_id={self.user_id}, role_id={self.role_id}, "
            f"turn={self.turn_index}, delta={self.delta})>"
        )


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
