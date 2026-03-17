from typing import Any, Optional

from pydantic import BaseModel, Field


class RetrievedDocument(BaseModel):
    collection: str
    content: str
    score: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGContext(BaseModel):
    role_knowledge: list[RetrievedDocument] = Field(default_factory=list)
    conversation_memory: list[RetrievedDocument] = Field(default_factory=list)

    def has_content(self) -> bool:
        return bool(self.role_knowledge or self.conversation_memory)
