#!/usr/bin/env python3
"""
数据库结构检查和修复工具
用于对比当前代码模型与云服数据库结构
"""

import asyncio
import sys
from sqlalchemy import inspect, text
from app.database.connection import DatabaseManager
from app.config import get_settings

async def check_database_schema():
    """检查数据库结构"""
    settings = get_settings()
    db_manager = DatabaseManager(settings.database_url)

    try:
        async with db_manager.engine.begin() as conn:
            inspector = inspect(conn.sync_engine)

            print("=" * 60)
            print("数据库结构检查报告")
            print("=" * 60)

            # 检查表是否存在
            existing_tables = set(inspector.get_table_names())
            expected_tables = {
                "roles",
                "role_relationship_prompts",
                "role_images",
                "user_roles",
                "chat_history",
                "role_relationship_configs",
            }

            print("\n【表存在性检查】")
            for table in expected_tables:
                status = "✓ 存在" if table in existing_tables else "✗ 缺失"
                print(f"  {table:20} {status}")

            # 详细检查每个表的字段
            print("\n【字段详细检查】")

            # 检查 roles 表
            if "roles" in existing_tables:
                print("\n  roles 表:")
                columns = {col["name"] for col in inspector.get_columns("roles")}
                expected_cols = {
                    "id", "role_id", "role_name", "system_prompt",
                    "scenario", "greeting_message", "avatar_url", "tags",
                    "is_active", "created_at", "updated_at"
                }
                for col in sorted(expected_cols):
                    status = "✓" if col in columns else "✗"
                    print(f"    {status} {col}")

            # 检查 role_images 表
            if "role_relationship_prompts" in existing_tables:
                print("\n  role_relationship_prompts 表:")
                columns = {col["name"] for col in inspector.get_columns("role_relationship_prompts")}
                expected_cols = {
                    "id", "role_id", "relationship", "prompt_text", "is_active",
                    "created_at", "updated_at"
                }
                for col in sorted(expected_cols):
                    status = "✓" if col in columns else "✗"
                    print(f"    {status} {col}")

            # 检查 role_images 表
            if "role_images" in existing_tables:
                print("\n  role_images 表:")
                columns = {col["name"] for col in inspector.get_columns("role_images")}
                expected_cols = {
                    "id", "role_id", "image_url", "image_type", "stage_key",
                    "trigger_type", "sort_order", "is_active", "meta_json",
                    "created_at", "updated_at"
                }
                for col in sorted(expected_cols):
                    status = "✓" if col in columns else "✗"
                    print(f"    {status} {col}")

            # 检查 user_roles 表
            if "user_roles" in existing_tables:
                print("\n  user_roles 表:")
                columns = {col["name"] for col in inspector.get_columns("user_roles")}
                expected_cols = {
                    "id", "user_id", "real_user_id", "role_id", "relationship", "is_current",
                    "first_interaction_at", "last_interaction_at", "created_at"
                }
                for col in sorted(expected_cols):
                    status = "✓" if col in columns else "✗"
                    print(f"    {status} {col}")

            # 检查 chat_history 表
            if "chat_history" in existing_tables:
                print("\n  chat_history 表:")
                columns = {col["name"] for col in inspector.get_columns("chat_history")}
                expected_cols = {
                    "id", "user_id", "role_id", "group_seq", "timestamp", "message_type", "content",
                    "image_url", "emotion_data", "decision_data", "meta_json",
                    "created_at"
                }
                for col in sorted(expected_cols):
                    status = "✓" if col in columns else "✗"
                    print(f"    {status} {col}")

            if "role_relationship_configs" in existing_tables:
                print("\n  role_relationship_configs 表:")
                columns = {col["name"] for col in inspector.get_columns("role_relationship_configs")}
                expected_cols = {
                    "id", "role_id", "initial_rv", "update_frequency", "max_negative_delta",
                    "max_positive_delta", "recent_window_size", "stage_names", "stage_floor_rv",
                    "stage_thresholds", "paid_boost_enabled", "meta_json", "created_at", "updated_at"
                }
                for col in sorted(expected_cols):
                    status = "✓" if col in columns else "✗"
                    print(f"    {status} {col}")

            # 检查索引
            print("\n【索引检查】")
            for table in expected_tables:
                if table in existing_tables:
                    indexes = inspector.get_indexes(table)
                    if indexes:
                        print(f"\n  {table}:")
                        for idx in indexes:
                            print(f"    - {idx['name']}: {', '.join(idx['column_names'])}")

            print("\n" + "=" * 60)
            print("检查完成")
            print("=" * 60)

    finally:
        await db_manager.close()

async def auto_fix_schema():
    """自动修复数据库结构"""
    settings = get_settings()
    db_manager = DatabaseManager(settings.database_url)

    try:
        print("\n开始自动修复数据库结构...")
        await db_manager.init_db()
        print("✓ 数据库结构已同步")
    finally:
        await db_manager.close()

async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--fix":
        await auto_fix_schema()
    else:
        await check_database_schema()

if __name__ == "__main__":
    asyncio.run(main())
