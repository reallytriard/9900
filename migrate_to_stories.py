#!/usr/bin/env python3
"""
迁移脚本：删除旧的 posts 表字段，创建新的 stories 和 sections 表
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from database import engine, Base
import models

def migrate():
    """创建新的 stories 和 sections 表"""
    connection = engine.connect()
    
    try:
        with connection.begin():
            print("Creating stories and sections tables...")
            
            # 删除旧的 stories 和 sections 表（如果存在）
            try:
                connection.execute(text("DROP TABLE IF EXISTS sections"))
                print("[+] Dropped old 'sections' table")
            except Exception as e:
                print(f"Note: sections table - {e}")
            
            try:
                connection.execute(text("DROP TABLE IF EXISTS stories"))
                print("[+] Dropped old 'stories' table")
            except Exception as e:
                print(f"Note: stories table - {e}")
            
            # 创建新表
            models.Story.__table__.create(engine, checkfirst=True)
            models.Section.__table__.create(engine, checkfirst=True)
            print("[+] Created 'stories' table")
            print("[+] Created 'sections' table")
        
        print("\n[OK] Migration completed successfully!")
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        connection.rollback()
    finally:
        connection.close()

if __name__ == "__main__":
    print("Starting database migration to stories/sections...\n")
    migrate()
