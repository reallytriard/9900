from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import json

class MediaBase(BaseModel):
    kind: str = Field(pattern="^(image|gif|video)$")
    url: str
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    credit: Optional[str] = None
    sort_order: int = 0

class MediaCreate(MediaBase):
    pass

class MediaRead(MediaBase):
    id: int
    class Config:
        from_attributes = True

class SectionBase(BaseModel):
    type: str
    data: str  # JSON string
    sort_order: int = 0

class SectionCreate(SectionBase):
    pass

class SectionRead(SectionBase):
    id: int
    story_id: int
    class Config:
        from_attributes = True

class StoryBase(BaseModel):
    title: Optional[str] = None
    version: Optional[str] = None
    standfirst: Optional[str] = None
    theme_font: Optional[str] = None
    theme_primary_color: Optional[str] = None

class StoryCreate(StoryBase):
    sections: List[SectionCreate] = []

class StoryUpdate(StoryBase):
    pass

class StoryRead(StoryBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sections: List[SectionRead] = []
    class Config:
        from_attributes = True

class PostBase(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    created_at: Optional[datetime] = None

class PostCreate(PostBase):
    media: List[MediaCreate] = []

class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    # allow resetting created_at if needed
    created_at: Optional[datetime] = None
    media: Optional[List[MediaCreate]] = None  # full replace when provided

class PostRead(PostBase):
    id: int
    updated_at: Optional[datetime] = None
    media: List[MediaRead] = []
    class Config:
        from_attributes = True
