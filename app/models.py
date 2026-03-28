from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.relationship_prompts import DEFAULT_RELATIONSHIP


class RoleImageInfo(BaseModel):
    id: int
    role_id: int
    image_url: str
    image_type: str = "avatar"
    stage_key: Optional[str] = None
    trigger_type: str = "manual"
    sort_order: int = 0
    is_active: bool = True
    meta_json: dict = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RoleRelationshipPromptInfo(BaseModel):
    id: Optional[int] = None
    role_id: int
    relationship: int
    relationship_key: str
    relationship_label: str
    prompt_text: str
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserState(BaseModel):
    user_id: str
    role_id: int
    user_name: Optional[str] = None
    relationship_level: int = DEFAULT_RELATIONSHIP  # 1=朋友, 2=恋人, 3=爱人
    character_mood: float = 0.1  # 0-1
    interaction_count: int = 0
    last_interaction: Optional[datetime] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

class EmotionResult(BaseModel):
    user_text: str
    user_emotion: str  # sad, happy, neutral, excited, cold
    emotion_score: float  # 0-1
    intent: str  # daily_chat, question, greeting
    keywords: list[str] = []

class DecisionResult(BaseModel):
    user_id: str
    reply_mood: str  # cold, warm, excited
    flirt_level: str  # none, low, medium, high
    split_level: int = 2  # 1=不切分 2=按句号切分(默认) 3=预留更细粒度切分
    allow_image: bool = False
    mood_delta: float = 0.1  # -0.2 ~ 0.2
    typing_delay_factor: float = 1.0  # 0.5 ~ 2.0

class DispatchTask(BaseModel):
    chat_id: str
    segments: list[str]
    typing_delay_factor: float = 1.0
    allow_image: bool = False

class RoleInfo(BaseModel):
    """角色信息模型"""
    id: int
    role_id: int
    role_name: str
    system_prompt: str
    scenario: Optional[str] = None
    greeting_message: Optional[str] = None
    avatar_url: Optional[str] = None
    opening_image_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    relationship: int = DEFAULT_RELATIONSHIP
    relationship_label: str = "朋友"
    relationship_prompts: list[RoleRelationshipPromptInfo] = Field(default_factory=list)
    role_images: list[RoleImageInfo] = Field(default_factory=list)
    is_active: bool = True
