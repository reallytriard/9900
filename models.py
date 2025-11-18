from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Story(Base):
    """Story 主表 - 存储 story.json 的元数据"""
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=True)
    version = Column(String(16), nullable=True)
    standfirst = Column(Text, nullable=True)
    theme_font = Column(String(128), nullable=True)
    theme_primary_color = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    sections = relationship("Section", back_populates="story", cascade="all, delete-orphan", order_by="Section.sort_order")

class Section(Base):
    """Section 表 - 存储 sections 数组中的每个 item"""
    __tablename__ = "sections"
    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(32), nullable=False)  # video, paragraph, pullquote, imagegroup, etc.
    sort_order = Column(Integer, default=0, nullable=False)
    
    # 存储 section 的完整 JSON 数据
    data = Column(Text, nullable=True)  # JSON string containing all section properties
    
    story = relationship("Story", back_populates="sections")

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    # 基本信息
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    author = Column(String(128), nullable=True)

    media = relationship("Media", back_populates="post", cascade="all, delete-orphan", order_by="Media.sort_order")

class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(16), nullable=False)  # image | gif | video
    url = Column(Text, nullable=False)         # absolute or relative URL
    caption = Column(Text, nullable=True)
    alt_text = Column(Text, nullable=True)
    credit = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)

    post = relationship("Post", back_populates="media")