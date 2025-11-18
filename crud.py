from sqlalchemy.orm import Session
from typing import Optional
import models, schemas
import json

def reorder_sections(db: Session, story_id: int, moving_section: Optional[models.Section] = None, target_index: Optional[int] = None):
    """Rebuild sequential sort_order, optionally inserting a moving section at target_index."""
    sections = (
        db.query(models.Section)
        .filter(models.Section.story_id == story_id)
        .order_by(models.Section.sort_order.asc(), models.Section.id.asc())
        .all()
    )
    if moving_section:
        sections = [s for s in sections if s.id != moving_section.id]
        insert_at = 0 if target_index is None else max(0, int(target_index))
        insert_at = min(insert_at, len(sections))
        sections.insert(insert_at, moving_section)
    for idx, section in enumerate(sections):
        if section.sort_order != idx:
            section.sort_order = idx

def create_post(db: Session, post: schemas.PostCreate) -> models.Post:
    db_post = models.Post(title=post.title, content=post.content, author=post.author, created_at=post.created_at or None)
    db.add(db_post)
    db.flush()  # so we have db_post.id
    # attach media
    for i, m in enumerate(post.media):
        media = models.Media(
            post_id=db_post.id,
            kind=m.kind,
            url=m.url,
            caption=m.caption,
            alt_text=m.alt_text,
            credit=m.credit,
            sort_order=m.sort_order if m.sort_order is not None else i
        )
        db.add(media)
    db.commit()
    db.refresh(db_post)
    return db_post

def get_posts(db: Session, skip: int = 0, limit: int = 50):
    return db.query(models.Post).offset(skip).limit(limit).all()

def get_post(db: Session, post_id: int):
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def delete_post(db: Session, post_id: int) -> bool:
    post = get_post(db, post_id)
    if not post:
        return False
    db.delete(post)
    db.commit()
    return True

def update_post(db: Session, post_id: int, payload: schemas.PostUpdate):
    post = get_post(db, post_id)
    if not post:
        return None
    # scalar fields
    if payload.title is not None:
        post.title = payload.title
    if payload.content is not None:
        post.content = payload.content
    if payload.author is not None:
        post.author = payload.author
    if payload.created_at is not None:
        post.created_at = payload.created_at

    # full replace media if provided
    if payload.media is not None:
        # delete old
        for m in list(post.media):
            db.delete(m)
        # add new
        for i, m in enumerate(payload.media):
            media = models.Media(
                post_id=post.id,
                kind=m.kind,
                url=m.url,
                caption=m.caption,
                alt_text=m.alt_text,
                credit=m.credit,
                sort_order=m.sort_order if m.sort_order is not None else i
            )
            db.add(media)

    db.commit()
    db.refresh(post)
    return post

# Story CRUD
def create_story(db: Session, story: schemas.StoryCreate) -> models.Story:
    db_story = models.Story(
        title=story.title,
        version=story.version,
        standfirst=story.standfirst,
        theme_font=story.theme_font,
        theme_primary_color=story.theme_primary_color
    )
    db.add(db_story)
    db.flush()  # so we have db_story.id
    
    # add sections
    for i, section in enumerate(story.sections):
        db_section = models.Section(
            story_id=db_story.id,
            type=section.type,
            data=section.data,
            sort_order=section.sort_order if section.sort_order is not None else i
        )
        db.add(db_section)
    
    db.commit()
    db.refresh(db_story)
    return db_story

def get_stories(db: Session, skip: int = 0, limit: int = 50):
    return db.query(models.Story).offset(skip).limit(limit).all()

def get_story(db: Session, story_id: int):
    return db.query(models.Story).filter(models.Story.id == story_id).first()

def get_latest_story(db: Session):
    return db.query(models.Story).order_by(models.Story.created_at.desc()).first()

def delete_story(db: Session, story_id: int) -> bool:
    story = get_story(db, story_id)
    if not story:
        return False
    db.delete(story)
    db.commit()
    return True

def update_story(db: Session, story_id: int, payload: schemas.StoryUpdate) -> Optional[models.Story]:
    story = get_story(db, story_id)
    if not story:
        return None
    if payload.title is not None:
        story.title = payload.title
    if payload.version is not None:
        story.version = payload.version
    if payload.standfirst is not None:
        story.standfirst = payload.standfirst
    if payload.theme_font is not None:
        story.theme_font = payload.theme_font
    if payload.theme_primary_color is not None:
        story.theme_primary_color = payload.theme_primary_color
    db.commit()
    db.refresh(story)
    return story

# Section CRUD
def get_sections(db: Session, story_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(models.Section)
    if story_id is not None:
        query = query.filter(models.Section.story_id == story_id)
    return query.order_by(models.Section.sort_order).offset(skip).limit(limit).all()

def get_section(db: Session, section_id: int):
    return db.query(models.Section).filter(models.Section.id == section_id).first()

def create_section(db: Session, section: schemas.SectionCreate, story_id: int) -> models.Section:
    db_section = models.Section(
        story_id=story_id,
        type=section.type,
        data=section.data,
        sort_order=section.sort_order
    )
    db.add(db_section)
    db.flush()
    reorder_sections(db, story_id, db_section, section.sort_order)
    db.commit()
    db.refresh(db_section)
    return db_section

def update_section(db: Session, section_id: int, section_type: str = None, data: str = None, sort_order: int = None) -> models.Section:
    section = get_section(db, section_id)
    if not section:
        return None
    if section_type is not None:
        section.type = section_type
    if data is not None:
        section.data = data
    if sort_order is not None:
        section.sort_order = sort_order
        db.flush()
        reorder_sections(db, section.story_id, section, sort_order)
    else:
        db.flush()
    db.commit()
    db.refresh(section)
    return section

def delete_section(db: Session, section_id: int) -> Optional[int]:
    section = get_section(db, section_id)
    if not section:
        return None
    story_id = section.story_id
    db.delete(section)
    db.flush()
    reorder_sections(db, story_id)
    db.commit()
    return story_id
