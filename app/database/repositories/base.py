from typing import TypeVar, Generic, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """基础 Repository 类，提供通用的 CRUD 操作"""

    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def create(self, obj: T) -> T:
        """创建记录"""
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_by_id(self, id: int) -> Optional[T]:
        """根据 ID 获取记录"""
        return await self.session.get(self.model, id)

    async def get_all(self) -> List[T]:
        """获取所有记录"""
        result = await self.session.execute(select(self.model))
        return result.scalars().all()

    async def update(self, obj: T) -> T:
        """更新记录"""
        await self.session.merge(obj)
        await self.session.flush()
        return obj

    async def delete(self, obj: T) -> None:
        """删除记录"""
        await self.session.delete(obj)
        await self.session.flush()

    async def commit(self) -> None:
        """提交事务"""
        await self.session.commit()

    async def rollback(self) -> None:
        """回滚事务"""
        await self.session.rollback()
