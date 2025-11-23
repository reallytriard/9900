#!/usr/bin/env python3
"""
迁移脚本：为现有的 posts 表添加 story.json 相关字段
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from database import engine

def migrate():
    """添加新的列到 posts 表"""
    connection = engine.connect()
    
    try:
        with connection.begin():
            # 获取所有现有的列名
            if connection.dialect.name == 'sqlite':
                result = connection.execute(text("PRAGMA table_info(posts)"))
                existing_columns = [row[1] for row in result]
            else:
                # MySQL
                result = connection.execute(text("""
                    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'posts'
                """))
                existing_columns = [row[0] for row in result]
            
            print(f"Existing columns: {existing_columns}\n")
            
            # 添加 version 列
            if 'version' not in existing_columns:
                try:
                    connection.execute(text("ALTER TABLE posts ADD COLUMN version VARCHAR(16)"))
                    print("[+] Added 'version' column")
                except Exception as e:
                    print(f"Note: version column - {e}")
            else:
                print("- 'version' column already exists")
            
            # 添加 standfirst 列
            if 'standfirst' not in existing_columns:
                try:
                    connection.execute(text("ALTER TABLE posts ADD COLUMN standfirst TEXT"))
                    print("[+] Added 'standfirst' column")
                except Exception as e:
                    print(f"Note: standfirst column - {e}")
            else:
                print("- 'standfirst' column already exists")
            
            # 添加 theme_font 列
            if 'theme_font' not in existing_columns:
                try:
                    connection.execute(text("ALTER TABLE posts ADD COLUMN theme_font VARCHAR(128)"))
                    print("[+] Added 'theme_font' column")
                except Exception as e:
                    print(f"Note: theme_font column - {e}")
            else:
                print("- 'theme_font' column already exists")
            
            # 添加 theme_primary_color 列
            if 'theme_primary_color' not in existing_columns:
                try:
                    connection.execute(text("ALTER TABLE posts ADD COLUMN theme_primary_color VARCHAR(16)"))
                    print("[+] Added 'theme_primary_color' column")
                except Exception as e:
                    print(f"Note: theme_primary_color column - {e}")
            else:
                print("- 'theme_primary_color' column already exists")
            
            # 添加 sections_data 列
            if 'sections_data' not in existing_columns:
                try:
                    connection.execute(text("ALTER TABLE posts ADD COLUMN sections_data TEXT"))
                    print("[+] Added 'sections_data' column")
                except Exception as e:
                    print(f"Note: sections_data column - {e}")
            else:
                print("- 'sections_data' column already exists")
        
        print("\n[OK] Migration completed successfully!")
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        connection.rollback()
    finally:
        connection.close()

if __name__ == "__main__":
    print("Starting database migration...\n")
    migrate()
