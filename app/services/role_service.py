from typing import List, Optional, Tuple

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    ChatHistory,
    Role,
    RoleImage,
    RoleRelationshipPrompt,
)
from app.database.repositories import (
    RoleImageRepository,
    RoleRelationshipPromptRepository,
    RoleRepository,
    UserRoleRepository,
)
from app.models import RoleImageInfo, RoleInfo, RoleRelationshipPromptInfo
from app.rag import rag_service
from app.relationship.prompting import select_relationship_prompt
from app.relationship_prompts import (
    DEFAULT_RELATIONSHIP,
    normalize_relationship,
    ordered_relationships,
    relationship_key,
    relationship_label,
)


class RoleService:
    """角色业务逻辑层"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.role_repo = RoleRepository(session)
        self.role_image_repo = RoleImageRepository(session)
        self.role_relationship_prompt_repo = RoleRelationshipPromptRepository(session)
        self.user_role_repo = UserRoleRepository(session)

    async def _resolve_user_relationship(
        self,
        *,
        user_id: str,
        role_id: int,
        fallback: Optional[int] = None,
    ) -> int:
        user_role = await self.user_role_repo.get_user_role(user_id, role_id)
        if user_role:
            return normalize_relationship(getattr(user_role, "relationship", None))
        return normalize_relationship(fallback)

    @staticmethod
    def _normalize_tags(tags: Optional[list[str]]) -> list[str]:
        if not tags:
            return []
        return [str(tag).strip() for tag in tags if str(tag).strip()]

    @staticmethod
    def _clean_prompt_text(prompt_text: Optional[str]) -> str:
        return str(prompt_text or "").strip()

    @staticmethod
    def _serialize_role_image(image: RoleImage) -> RoleImageInfo:
        return RoleImageInfo(
            id=image.id,
            role_id=image.role_id,
            image_url=image.image_url,
            image_type=image.image_type,
            stage_key=image.stage_key,
            trigger_type=image.trigger_type,
            sort_order=image.sort_order,
            is_active=image.is_active,
            meta_json=dict(getattr(image, "meta_json", None) or {}),
            created_at=getattr(image, "created_at", None),
            updated_at=getattr(image, "updated_at", None),
        )

    @staticmethod
    def _serialize_relationship_prompt(
        prompt: RoleRelationshipPrompt,
    ) -> RoleRelationshipPromptInfo:
        relationship = normalize_relationship(prompt.relationship)
        return RoleRelationshipPromptInfo(
            id=prompt.id,
            role_id=prompt.role_id,
            relationship=relationship,
            relationship_key=relationship_key(relationship),
            relationship_label=relationship_label(relationship),
            prompt_text=str(prompt.prompt_text or ""),
            is_active=bool(prompt.is_active),
            created_at=getattr(prompt, "created_at", None),
            updated_at=getattr(prompt, "updated_at", None),
        )

    @classmethod
    def normalize_relationship_prompts(
        cls,
        *,
        relationship_prompts: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        normalized: dict[int, dict] = {}
        for item in relationship_prompts or []:
            relationship = normalize_relationship(item.get("relationship"))
            prompt_text = cls._clean_prompt_text(item.get("prompt_text"))
            if not prompt_text:
                continue
            normalized[relationship] = {
                "id": item.get("id"),
                "role_id": item.get("role_id"),
                "relationship": relationship,
                "relationship_key": relationship_key(relationship),
                "relationship_label": relationship_label(relationship),
                "prompt_text": prompt_text,
                "is_active": bool(item.get("is_active", True)),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }

        fallback_friend = (
            normalized.get(1, {}).get("prompt_text")
            or cls._clean_prompt_text(system_prompt)
        )
        if fallback_friend:
            normalized[1] = {
                **normalized.get(1, {}),
                "relationship": 1,
                "relationship_key": relationship_key(1),
                "relationship_label": relationship_label(1),
                "prompt_text": fallback_friend,
                "is_active": bool(normalized.get(1, {}).get("is_active", True)),
            }

        return [
            normalized[relationship]
            for relationship in ordered_relationships()
            if normalized.get(relationship, {}).get("prompt_text")
        ]

    @classmethod
    def resolve_role_prompt(cls, role: RoleInfo, relationship: Optional[int]) -> str:
        return select_relationship_prompt(role, relationship)

    async def _build_role_info(self, role: Role) -> RoleInfo:
        images = await self.role_image_repo.list_by_role(role.id)
        role_images = [self._serialize_role_image(image) for image in images]
        opening_image_url = next(
            (
                image.image_url
                for image in role_images
                if image.is_active and image.image_type == "opening"
            ),
            None,
        )

        prompt_rows = await self.role_relationship_prompt_repo.list_by_role(role.id)
        normalized_prompts = self.normalize_relationship_prompts(
            relationship_prompts=[
                {
                    "id": prompt.id,
                    "role_id": prompt.role_id,
                    "relationship": prompt.relationship,
                    "prompt_text": prompt.prompt_text,
                    "is_active": prompt.is_active,
                    "created_at": getattr(prompt, "created_at", None),
                    "updated_at": getattr(prompt, "updated_at", None),
                }
                for prompt in prompt_rows
                if bool(prompt.is_active) and self._clean_prompt_text(prompt.prompt_text)
            ],
            system_prompt=role.system_prompt,
        )
        relationship_prompt_infos = [
            RoleRelationshipPromptInfo(
                id=item.get("id"),
                role_id=item.get("role_id") or role.id,
                relationship=item["relationship"],
                relationship_key=item["relationship_key"],
                relationship_label=item["relationship_label"],
                prompt_text=item["prompt_text"],
                is_active=bool(item.get("is_active", True)),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
            )
            for item in normalized_prompts
        ]
        prompt_lookup = {
            item.relationship: self._clean_prompt_text(item.prompt_text)
            for item in relationship_prompt_infos
            if self._clean_prompt_text(item.prompt_text)
        }
        friend_prompt = prompt_lookup.get(1) or self._clean_prompt_text(role.system_prompt)

        return RoleInfo(
            id=role.id,
            role_id=role.role_id,
            role_name=role.role_name,
            system_prompt=friend_prompt,
            scenario=role.scenario,
            greeting_message=role.greeting_message,
            avatar_url=role.avatar_url,
            opening_image_url=opening_image_url or role.avatar_url,
            tags=self._normalize_tags(getattr(role, "tags", None)),
            relationship=DEFAULT_RELATIONSHIP,
            relationship_label=relationship_label(DEFAULT_RELATIONSHIP),
            relationship_prompts=relationship_prompt_infos,
            role_images=role_images,
            is_active=role.is_active,
        )

    async def _sync_role_relationship_prompts(
        self,
        role_id: int,
        relationship_prompts: list[dict],
    ) -> None:
        existing_rows = await self.role_relationship_prompt_repo.list_by_role(role_id)
        existing_map = {
            normalize_relationship(prompt.relationship): prompt for prompt in existing_rows
        }
        incoming_map = {
            normalize_relationship(item["relationship"]): item
            for item in relationship_prompts
            if self._clean_prompt_text(item.get("prompt_text"))
        }

        for relationship in ordered_relationships():
            incoming = incoming_map.get(relationship)
            existing = existing_map.get(relationship)

            if incoming:
                prompt_text = self._clean_prompt_text(incoming.get("prompt_text"))
                if existing:
                    existing.prompt_text = prompt_text
                    existing.is_active = bool(incoming.get("is_active", True))
                    await self.role_relationship_prompt_repo.update(existing)
                else:
                    await self.role_relationship_prompt_repo.create(
                        RoleRelationshipPrompt(
                            role_id=role_id,
                            relationship=relationship,
                            prompt_text=prompt_text,
                            is_active=bool(incoming.get("is_active", True)),
                        )
                    )
                continue

            if existing:
                existing.prompt_text = ""
                existing.is_active = False
                await self.role_relationship_prompt_repo.update(existing)

    async def get_role(self, role_id: int) -> Optional[RoleInfo]:
        """获取角色配置"""
        role = await self.role_repo.get_by_id(role_id)
        if role:
            return await self._build_role_info(role)
        return None

    async def get_role_by_name(self, role_name: str) -> Optional[RoleInfo]:
        """根据名称获取角色"""
        role = await self.role_repo.get_by_name(role_name)
        if role:
            return await self._build_role_info(role)
        return None

    async def get_all_active_roles(self) -> List[RoleInfo]:
        """获取所有激活的角色"""
        roles = await self.role_repo.get_active_roles()
        return [await self._build_role_info(role) for role in roles]

    async def get_active_roles_page(
        self,
        *,
        page: int,
        page_size: int,
    ) -> Tuple[List[RoleInfo], int]:
        roles, total = await self.role_repo.get_active_roles_paginated(
            page=page,
            page_size=page_size,
        )
        return [await self._build_role_info(role) for role in roles], total

    async def get_all_roles(self) -> List[RoleInfo]:
        roles = await self.role_repo.get_all_roles()
        return [await self._build_role_info(role) for role in roles]

    async def get_user_current_role(self, user_id: str) -> Optional[RoleInfo]:
        """获取用户当前选择的角色"""
        user_role = await self.user_role_repo.get_user_current_role(user_id)
        if user_role:
            role = await self.role_repo.get_by_id(user_role.role_id)
            if role:
                role_info = await self._build_role_info(role)
                role_info.relationship = await self._resolve_user_relationship(
                    user_id=user_id,
                    role_id=user_role.role_id,
                    fallback=user_role.relationship,
                )
                role_info.relationship_label = relationship_label(role_info.relationship)
                return role_info
        return None

    async def set_user_role(self, user_id: str, role_id: int) -> RoleInfo:
        """设置用户的当前角色"""
        user_role = await self.user_role_repo.set_current_role(user_id, role_id)
        await self.session.commit()
        role = await self.role_repo.get_by_id(role_id)
        role_info = await self._build_role_info(role)
        role_info.relationship = await self._resolve_user_relationship(
            user_id=user_id,
            role_id=role_id,
            fallback=user_role.relationship,
        )
        role_info.relationship_label = relationship_label(role_info.relationship)
        return role_info

    async def get_user_roles(self, user_id: str) -> List[RoleInfo]:
        """获取用户的所有角色"""
        user_roles = await self.user_role_repo.get_user_roles(user_id)
        roles = []
        for user_role in user_roles:
            role = await self.role_repo.get_by_id(user_role.role_id)
            if role:
                role_info = await self._build_role_info(role)
                role_info.relationship = await self._resolve_user_relationship(
                    user_id=user_id,
                    role_id=user_role.role_id,
                    fallback=user_role.relationship,
                )
                role_info.relationship_label = relationship_label(role_info.relationship)
                roles.append(role_info)
        return roles

    async def get_user_roles_page(
        self,
        user_id: str,
        *,
        page: int,
        page_size: int,
    ) -> Tuple[List[RoleInfo], int]:
        user_roles, total = await self.user_role_repo.get_user_roles_paginated(
            user_id,
            page=page,
            page_size=page_size,
        )
        roles = []
        for user_role in user_roles:
            role = await self.role_repo.get_by_id(user_role.role_id)
            if not role:
                continue
            role_info = await self._build_role_info(role)
            role_info.relationship = await self._resolve_user_relationship(
                user_id=user_id,
                role_id=user_role.role_id,
                fallback=user_role.relationship,
            )
            role_info.relationship_label = relationship_label(role_info.relationship)
            roles.append(role_info)
        return roles, total

    async def get_user_role_relationship(self, user_id: str, role_id: int) -> int:
        user_role = await self.user_role_repo.get_user_role(user_id, role_id)
        if not user_role:
            return DEFAULT_RELATIONSHIP
        return await self._resolve_user_relationship(
            user_id=user_id,
            role_id=role_id,
            fallback=user_role.relationship,
        )

    async def reset_user_role(self, user_id: str, role_id: int) -> bool:
        user_role = await self.user_role_repo.get_user_role(user_id, role_id)
        if not user_role:
            return False

        await self.session.execute(
            delete(ChatHistory).where(
                ChatHistory.user_id == user_id,
                ChatHistory.role_id == role_id,
            )
        )
        await self.user_role_repo.delete_user_role(user_id, role_id)
        await self.session.commit()

        try:
            await rag_service.delete_conversation_memory(user_id=user_id, role_id=role_id)
        except Exception:
            pass

        return True

    async def create_role(
        self,
        *,
        role_id: int,
        role_name: str,
        system_prompt: str,
        scenario: Optional[str] = None,
        greeting_message: Optional[str] = None,
        avatar_url: Optional[str] = None,
        tags: Optional[list[str]] = None,
        relationship_prompts: Optional[list[dict]] = None,
        is_active: bool = True,
    ) -> RoleInfo:
        normalized_prompts = self.normalize_relationship_prompts(
            relationship_prompts=relationship_prompts,
            system_prompt=system_prompt,
        )
        friend_prompt = next(
            (
                item["prompt_text"]
                for item in normalized_prompts
                if item["relationship"] == DEFAULT_RELATIONSHIP
            ),
            self._clean_prompt_text(system_prompt),
        )
        role = Role(
            role_id=role_id,
            role_name=role_name,
            system_prompt=friend_prompt,
            scenario=scenario,
            greeting_message=greeting_message,
            avatar_url=avatar_url,
            tags=self._normalize_tags(tags),
            is_active=is_active,
        )
        await self.role_repo.create(role)
        await self._sync_role_relationship_prompts(role.id, normalized_prompts)
        await self.session.commit()
        return await self.get_role(role.id)

    async def update_role(
        self,
        role_id: int,
        *,
        business_role_id: Optional[int] = None,
        role_name: str,
        system_prompt: str,
        scenario: Optional[str] = None,
        greeting_message: Optional[str] = None,
        avatar_url: Optional[str] = None,
        tags: Optional[list[str]] = None,
        relationship_prompts: Optional[list[dict]] = None,
        is_active: bool = True,
    ) -> Optional[RoleInfo]:
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            return None

        normalized_prompts = self.normalize_relationship_prompts(
            relationship_prompts=relationship_prompts,
            system_prompt=system_prompt,
        )
        friend_prompt = next(
            (
                item["prompt_text"]
                for item in normalized_prompts
                if item["relationship"] == DEFAULT_RELATIONSHIP
            ),
            self._clean_prompt_text(system_prompt),
        )
        role.role_name = role_name
        if business_role_id is not None:
            role.role_id = business_role_id
        role.system_prompt = friend_prompt
        role.scenario = scenario
        role.greeting_message = greeting_message
        role.avatar_url = avatar_url
        role.tags = self._normalize_tags(tags)
        role.is_active = is_active
        await self.role_repo.update(role)
        await self._sync_role_relationship_prompts(role_id, normalized_prompts)
        await self.session.commit()
        return await self.get_role(role_id)

    async def list_role_relationship_prompts(
        self,
        role_id: int,
    ) -> list[RoleRelationshipPromptInfo]:
        prompts = await self.role_relationship_prompt_repo.list_by_role(role_id)
        return [self._serialize_relationship_prompt(prompt) for prompt in prompts]

    async def list_role_images(self, role_id: int) -> list[RoleImageInfo]:
        images = await self.role_image_repo.list_by_role(role_id)
        return [self._serialize_role_image(image) for image in images]

    async def create_role_image(
        self,
        *,
        role_id: int,
        image_url: str,
        image_type: str = "avatar",
        stage_key: Optional[str] = None,
        trigger_type: str = "manual",
        sort_order: int = 0,
        is_active: bool = True,
        meta_json: Optional[dict] = None,
    ) -> RoleImageInfo:
        image = RoleImage(
            role_id=role_id,
            image_url=image_url,
            image_type=image_type or "avatar",
            stage_key=stage_key or None,
            trigger_type=trigger_type or "manual",
            sort_order=sort_order,
            is_active=is_active,
            meta_json=meta_json or {},
        )
        await self.role_image_repo.create(image)
        await self.session.commit()
        return self._serialize_role_image(image)

    async def update_role_image(
        self,
        image_id: int,
        *,
        image_url: str,
        image_type: str = "avatar",
        stage_key: Optional[str] = None,
        trigger_type: str = "manual",
        sort_order: int = 0,
        is_active: bool = True,
        meta_json: Optional[dict] = None,
    ) -> Optional[RoleImageInfo]:
        image = await self.role_image_repo.get_by_id(image_id)
        if not image:
            return None
        image.image_url = image_url
        image.image_type = image_type or "avatar"
        image.stage_key = stage_key or None
        image.trigger_type = trigger_type or "manual"
        image.sort_order = sort_order
        image.is_active = is_active
        image.meta_json = meta_json or {}
        await self.role_image_repo.update(image)
        await self.session.commit()
        return self._serialize_role_image(image)

    async def get_role_opening_image(self, role_id: int) -> Optional[RoleImageInfo]:
        images = await self.role_image_repo.list_active_by_role(role_id, image_type="opening")
        if images:
            return self._serialize_role_image(images[0])
        role = await self.role_repo.get_by_id(role_id)
        if role and role.avatar_url:
            return RoleImageInfo(
                id=0,
                role_id=role_id,
                image_url=role.avatar_url,
                image_type="avatar",
                stage_key="fallback",
                trigger_type="manual",
                sort_order=0,
                is_active=True,
                meta_json={},
            )
        return None
