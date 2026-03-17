#!/usr/bin/env python
"""
数据库初始化脚本
用法: python scripts/init_db.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
from app.database.connection import init_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    try:
        logger.info("开始初始化数据库...")
        await init_database()
        logger.info("✓ 数据库初始化完成")
    except Exception as e:
        logger.error(f"✗ 数据库初始化失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
