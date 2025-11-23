from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path, PurePosixPath
import json
import os
import shutil
import uuid
import logging
from datetime import datetime
import models, schemas, crud
from database import SessionLocal, engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Posts Backend", version="1.0.0")

backend_dir = Path(__file__).resolve().parent
project_root = backend_dir.parent

def _discover_default_story_path() -> Path:
    """Locate a sensible default story.json when env var is not provided.

    Preference order:
      1. capstone-frontend/public/story.json inside the current project
      2. capstone-frontend/public/story.json one directory above (GitHub Classroom root)
      3. capstone-backend/public/story.json if it exists
    """
    candidate_public_dirs = [
        project_root / "capstone-frontend" / "public",
        project_root.parent / "capstone-frontend" / "public",
        backend_dir / "public",
    ]

    for public_dir in candidate_public_dirs:
        story_path = public_dir / "story.json"
        if story_path.exists():
            return story_path

    for public_dir in candidate_public_dirs:
        if public_dir.is_dir():
            return public_dir / "story.json"

    raise FileNotFoundError(
        "Unable to locate story.json automatically. "
        "Set STORY_JSON_PATH environment variable to the desired file."
    )


_default_story_json_path = _discover_default_story_path()
STORY_JSON_PATH = Path(os.getenv("STORY_JSON_PATH", _default_story_json_path))
PUBLIC_DIR = STORY_JSON_PATH.parent
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", backend_dir / "static_media")).resolve()
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
MEDIA_URL_PREFIX = os.getenv("MEDIA_URL_PREFIX", "/media")
if not MEDIA_URL_PREFIX.startswith("/"):
    MEDIA_URL_PREFIX = f"/{MEDIA_URL_PREFIX}"
MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", "http://localhost:8888").rstrip("/")
app.mount(MEDIA_URL_PREFIX, StaticFiles(directory=MEDIA_ROOT), name="media")


def build_story_payload(story: models.Story) -> dict:
    """Assemble a story payload compatible with story.json."""
    payload = {
        "id": story.id,
        "version": story.version or "1.0",
        "title": story.title or "Story",
        "standfirst": story.standfirst or "",
        "theme": {
            "font": story.theme_font or "Montserrat",
            "primaryColor": story.theme_primary_color or "#00007a",
        },
        "sections": [],
    }

    for section in story.sections:
        raw_data = section.data or "{}"
        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError:
            parsed = {"type": section.type}
        payload["sections"].append(parsed)

    return payload


def sync_story_json(db: Session, story_id: int) -> Optional[dict]:
    """Write the current story state back to story.json for static fallback."""
    story = crud.get_story(db, story_id)
    if not story:
        return None

    payload = build_story_payload(story)

    if not STORY_JSON_PATH.exists():
        logging.getLogger(__name__).warning(
            "story.json not found at %s; skipping sync to avoid creating new files",
            STORY_JSON_PATH,
        )
        return payload

    try:
        STORY_JSON_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logging.getLogger(__name__).warning("Failed to sync story.json: %s", exc)
    return payload

# CORS for Vite dev (5173) and local file preview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/healthz")
def health():
    return {"ok": True}

@app.post("/posts", response_model=schemas.PostRead)
def create_post(post: schemas.PostCreate, db: Session = Depends(get_db)):
    created = crud.create_post(db, post)
    return created

@app.get("/posts", response_model=List[schemas.PostRead])
def list_posts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_posts(db, skip=skip, limit=limit)

@app.get("/posts/{post_id}", response_model=schemas.PostRead)
def read_post(post_id: int, db: Session = Depends(get_db)):
    post = crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@app.put("/posts/{post_id}", response_model=schemas.PostRead)
@app.patch("/posts/{post_id}", response_model=schemas.PostRead)
def update_post(post_id: int, payload: schemas.PostUpdate, db: Session = Depends(get_db)):
    post = crud.update_post(db, post_id, payload)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@app.delete("/posts/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_post(db, post_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"deleted": True, "id": post_id}

# Sections CRUD API
@app.get("/sections", response_model=List[schemas.SectionRead])
def list_sections(story_id: Optional[int] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_sections(db, story_id=story_id, skip=skip, limit=limit)

@app.get("/sections/{section_id}", response_model=schemas.SectionRead)
def read_section(section_id: int, db: Session = Depends(get_db)):
    section = crud.get_section(db, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section

@app.post("/sections", response_model=schemas.SectionRead)
def create_section(section: schemas.SectionCreate, story_id: int, db: Session = Depends(get_db)):
    created = crud.create_section(db, section, story_id)
    sync_story_json(db, created.story_id)
    return created

@app.patch("/sections/{section_id}", response_model=schemas.SectionRead)
def update_section_endpoint(section_id: int, section_update: dict, db: Session = Depends(get_db)):
    section = crud.update_section(
        db, section_id,
        section_type=section_update.get("type"),
        data=section_update.get("data"),
        sort_order=section_update.get("sort_order")
    )
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    sync_story_json(db, section.story_id)
    return section

@app.delete("/sections/{section_id}")
def delete_section_endpoint(section_id: int, db: Session = Depends(get_db)):
    story_id = crud.delete_section(db, section_id)
    if story_id is None:
        raise HTTPException(status_code=404, detail="Section not found")
    sync_story_json(db, story_id)
    return {"deleted": True, "id": section_id}

# Get full story data (compatible with story.json format)
@app.get("/story")
def get_story(version: Optional[int] = None, db: Session = Depends(get_db)):
    """获取完整的 story 数据（兼容 story.json 格式）"""
    story = crud.get_latest_story(db)
    if not story:
        raise HTTPException(status_code=404, detail="No story found")

    if version is not None:
        snapshot = crud.get_story_version(db, story.id, version)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Version not found")
        try:
            payload = json.loads(snapshot.payload)
            payload["versionNumber"] = snapshot.version_number
            return payload
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Corrupted version payload")

    latest_snapshot = crud.get_story_version(db, story.id)
    payload = build_story_payload(story)
    if latest_snapshot:
        payload["versionNumber"] = latest_snapshot.version_number
    return payload

@app.post("/story/publish")
def publish_story(db: Session = Depends(get_db)):
    story = crud.get_latest_story(db)
    if not story:
        raise HTTPException(status_code=404, detail="No story found")
    payload = build_story_payload(story)
    version_entry = crud.record_story_version(db, story.id, payload)
    if not version_entry:
        raise HTTPException(status_code=500, detail="Unable to create version")
    return {
        "versionNumber": version_entry.version_number,
        "createdAt": version_entry.created_at
    }

@app.patch("/story/{story_id}")
def update_story(story_id: int, payload: schemas.StoryUpdate, db: Session = Depends(get_db)):
    updated = crud.update_story(db, story_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Story not found")
    sync_story_json(db, story_id)
    return build_story_payload(updated)

# Optional: Import story.json from the frontend and convert sections into posts
@app.post("/import/story", response_model=List[schemas.PostRead])
def import_story(frontend_root: Optional[str] = None, db: Session = Depends(get_db)):
    # If not provided, assume /mnt/data/project/.../frontend/public/story.json in this environment
    if not frontend_root:
        frontend_root = "F:/work/edit-web/frontend/public"
    story_path = Path(frontend_root) / "story.json"
    if not story_path.exists():
        raise HTTPException(status_code=404, detail=f"story.json not found at {story_path}")
    story = json.loads(story_path.read_text(encoding="utf-8"))

    results = []
    # Strategy: one Post per section with all textual content, collect media URLs.
    sections = story.get("sections", [])
    for idx, sec in enumerate(sections):
        media_list = []
        text_blob = []

        t = sec.get("type")
        if t in ("paragraph",):
            content = sec.get("content", "")
            text_blob.append(content)
        if t in ("pullquote",):
            text_blob.append(sec.get("text", ""))
            if sec.get("cite"):
                text_blob.append(f"— {sec.get('cite')}")
        if t in ("imagegif",):
            src = sec.get("src")
            if src:
                media_list.append({"kind": "gif" if src.lower().endswith(('.gif')) else "image", "url": src, "caption": sec.get("caption"), "alt_text": sec.get("alt", ""), "credit": sec.get("credit", ""), "sort_order": 0})
        if t in ("video",):
            src = sec.get("src")
            if src:
                media_list.append({"kind": "video", "url": src, "caption": sec.get("caption"), "alt_text": sec.get("alt", ""), "credit": sec.get("credit", ""), "sort_order": 0})
        if t in ("imagegroup",):
            imgs = sec.get("images", [])
            for i, im in enumerate(imgs):
                media_list.append({"kind": "image", "url": im.get("src"), "caption": im.get("caption"), "alt_text": im.get("alt", ""), "credit": im.get("credit", ""), "sort_order": i})

        title = story.get("title", f"Section {idx+1}")
        content_joined = "\n\n".join([s for s in text_blob if s])

        created = crud.create_post(db, schemas.PostCreate(
            title=title,
            content=content_joined or None,
            media=[schemas.MediaCreate(**m) for m in media_list]
        ))
        results.append(created)

    return results

# Import story.json from uploaded file
@app.post("/import/story_upload", response_model=schemas.StoryRead)
async def import_story_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """从上传的文件导入 story.json"""
    try:
        # 读取上传的文件
        content = await file.read()
        story_json = json.loads(content.decode('utf-8'))
        
        title = story_json.get("title") or "Story"
        standfirst = story_json.get("standfirst") or ""
        version = story_json.get("version", "1.0")
        theme = story_json.get("theme", {})
        theme_font = theme.get("font")
        theme_primary_color = theme.get("primaryColor")
        sections = story_json.get("sections", [])
        
        # 创建 SectionCreate 对象数组
        section_creates = []
        for i, section in enumerate(sections):
            section_creates.append(schemas.SectionCreate(
                type=section.get("type", "unknown"),
                data=json.dumps(section, ensure_ascii=False),
                sort_order=i
            ))
        
        # 创建 Story
        created = crud.create_story(db, schemas.StoryCreate(
            title=title,
            version=version,
            standfirst=standfirst,
            theme_font=theme_font,
            theme_primary_color=theme_primary_color,
            sections=section_creates
        ))
        sync_story_json(db, created.id)
        return created
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Import entire story.json as ONE post (merge all sections)
@app.post("/import/story_merged", response_model=schemas.PostRead)
def import_story_merged(frontend_root: Optional[str] = None, db: Session = Depends(get_db)):
    if not frontend_root:
        frontend_root = "F:/work/edit-web/frontend/public"
    story_path = Path(frontend_root) / "story.json"
    if not story_path.exists():
        raise HTTPException(status_code=404, detail=f"story.json not found at {story_path}")
    story = json.loads(story_path.read_text(encoding="utf-8"))

    title = story.get("title") or "Story"
    standfirst = story.get("standfirst") or ""
    version = story.get("version", "1.0")
    theme = story.get("theme", {})
    theme_font = theme.get("font")
    theme_primary_color = theme.get("primaryColor")
    sections = story.get("sections", [])
    
    # 将 sections 转换为 JSON 字符串存储
    sections_json = json.dumps(sections, ensure_ascii=False)

    # Collect all text and media with stable order
    text_parts = []
    media_list = []
    m_index = 0

    # include standfirst up front if present
    if standfirst:
        text_parts.append(standfirst)

    for sec in sections:
        t = sec.get("type")
        # text-like
        if t == "paragraph":
            content = sec.get("content", "")
            if content:
                text_parts.append(content)
        elif t == "pullquote":
            txt = sec.get("text", "")
            cite = sec.get("cite") or ""
            if txt:
                if cite:
                    text_parts.append(f"{txt}\n— {cite}")
                else:
                    text_parts.append(txt)
        # media-like
        elif t == "imagegif":
            src = sec.get("src")
            if src:
                media_list.append({
                    "kind": "gif" if src.lower().endswith(('.gif',)) else "image",
                    "url": src,
                    "caption": sec.get("caption"),
                    "alt_text": sec.get("alt", ""),
                    "credit": sec.get("credit", ""),
                    "sort_order": m_index
                })
                m_index += 1
        elif t == "video":
            src = sec.get("src")
            if src:
                media_list.append({
                    "kind": "video",
                    "url": src,
                    "caption": sec.get("caption"),
                    "alt_text": sec.get("alt", ""),
                    "credit": sec.get("credit", ""),
                    "sort_order": m_index
                })
                m_index += 1
        elif t == "imagegroup":
            imgs = sec.get("images", [])
            for im in imgs:
                src = im.get("src")
                if not src: 
                    continue
                media_list.append({
                    "kind": "image",
                    "url": src,
                    "caption": im.get("caption"),
                    "alt_text": im.get("alt", ""),
                    "credit": im.get("credit", ""),
                    "sort_order": m_index
                })
                m_index += 1
        # ignore other unknown types gracefully

    merged_text = "\n\n".join([s for s in text_parts if s])
    created = crud.create_post(db, schemas.PostCreate(
        title=title,
        content=merged_text or None,
        media=[schemas.MediaCreate(**m) for m in media_list],
        version=version,
        standfirst=standfirst,
        theme_font=theme_font,
        theme_primary_color=theme_primary_color,
        sections_data=sections_json
    ))
    return created

# 文件上传 API
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    target_path: Optional[str] = Form(None)
):
    """保存上传的文件到 MEDIA_ROOT，并返回可直接访问的 URL。

    - file: 上传的二进制文件
    - target_path: （可选）相对路径，例如 /media/uploads/foo.jpg。若未提供则自动生成。
    """
    try:
        original_name = Path(file.filename or "upload")
        extension = original_name.suffix

        if target_path:
            pure_target = PurePosixPath(target_path.lstrip('/'))
            if any(part == '..' for part in pure_target.parts):
                raise HTTPException(status_code=400, detail="非法目标路径")
            if not pure_target.parts:
                raise HTTPException(status_code=400, detail="目标路径不能为空")
            relative_path = Path(*pure_target.parts)
        else:
            today = datetime.utcnow()
            generated_name = f"{uuid.uuid4().hex}{extension}"
            relative_path = Path("uploads") / today.strftime("%Y/%m/%d") / generated_name

        full_path = (MEDIA_ROOT / relative_path).resolve()
        if MEDIA_ROOT not in full_path.parents and full_path != MEDIA_ROOT:
            raise HTTPException(status_code=400, detail="目标路径不在允许的 media 目录内")

        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        media_prefix = MEDIA_URL_PREFIX.rstrip("/")
        if media_prefix:
            public_path = f"{media_prefix}/{relative_path.as_posix()}"
        else:
            public_path = f"/{relative_path.as_posix()}"
        public_url = f"{MEDIA_BASE_URL}{public_path}"

        return {
            "success": True,
            "url": public_url,
            "path": f"/{relative_path.as_posix()}",
            "filename": full_path.name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
