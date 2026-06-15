"""modules/career/router.py — Career cockpit REST endpoints (CAR-1).

Mounts at ``/career`` via the registry (``MODULE``). Locked envelope
``{success, data, warning?}`` (core.responses.ok). Business logic in service.py;
this layer is HTTP shape + status codes only. No routine (user-driven CRUD).

Endpoints:
  CV    GET  /career/cv            → parsed sections + meta + proof links
        GET  /career/cv/raw        → raw markdown (export / copy)
        PUT  /career/cv            → replace raw markdown (edit)
  Blog  GET  /career/blog          → all posts (newest-updated first)
        POST /career/blog          → create
        GET  /career/blog/{id}     → one post (404 if absent)
        PUT  /career/blog/{id}     → update (404 if absent)
        DELETE /career/blog/{id}   → delete (404 if absent)
  Demo  GET  /career/demo          → all demos
        POST /career/demo          → create
        GET  /career/demo/{id}     → one demo (404 if absent)
        PUT  /career/demo/{id}     → update (404 if absent)
        DELETE /career/demo/{id}   → delete (404 if absent)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import BlogInput, CvUpdateInput, DemoInput

logger = logging.getLogger("life-os.career.router")

router = APIRouter(tags=["career"])


# --------------------------------------------------------------------------- #
# CV                                                                            #
# --------------------------------------------------------------------------- #
@router.get("/cv")
def get_cv():
    """The living CV, parsed into header meta + ordered sections (with proof chips)."""
    cv = service.get_cv()
    return ok(data=cv.model_dump())


@router.get("/cv/raw")
def get_cv_raw():
    """The CV's raw markdown — for export / copy."""
    return ok(data={"markdown": service.get_cv_raw()})


@router.put("/cv")
def update_cv(body: CvUpdateInput):
    """Replace the CV's raw markdown (edit). Returns the re-parsed CV."""
    cv = service.update_cv(body.markdown)
    return ok(data=cv.model_dump())


# --------------------------------------------------------------------------- #
# Blog                                                                          #
# --------------------------------------------------------------------------- #
@router.get("/blog")
def list_blog():
    """All blog posts, newest-updated first."""
    posts, warnings = service.list_blog()
    return ok(
        data=[p.model_dump() for p in posts],
        warning="; ".join(warnings) if warnings else None,
    )


@router.post("/blog")
def create_blog(body: BlogInput):
    """Create a blog post (server-set id + timestamps)."""
    post = service.create_blog(body)
    return ok(data=post.model_dump())


@router.get("/blog/{post_id}")
def get_blog(post_id: str):
    """One blog post. 404 if absent/malformed."""
    post = service.get_blog(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail=f"blog post {post_id!r} not found")
    return ok(data=post.model_dump())


@router.put("/blog/{post_id}")
def update_blog(post_id: str, body: BlogInput):
    """Update a blog post (preserve createdAt). 404 if absent."""
    post = service.update_blog(post_id, body)
    if post is None:
        raise HTTPException(status_code=404, detail=f"blog post {post_id!r} not found")
    return ok(data=post.model_dump())


@router.delete("/blog/{post_id}")
def delete_blog(post_id: str):
    """Delete a blog post (one git commit). 404 if absent."""
    if not service.delete_blog(post_id):
        raise HTTPException(status_code=404, detail=f"blog post {post_id!r} not found")
    return ok(data={"deleted": post_id})


# --------------------------------------------------------------------------- #
# Demo / showcase                                                              #
# --------------------------------------------------------------------------- #
@router.get("/demo")
def list_demo():
    """All demo / showcase items, newest-updated first."""
    items, warnings = service.list_demo()
    return ok(
        data=[i.model_dump() for i in items],
        warning="; ".join(warnings) if warnings else None,
    )


@router.post("/demo")
def create_demo(body: DemoInput):
    """Create a demo item (server-set id + timestamps)."""
    item = service.create_demo(body)
    return ok(data=item.model_dump())


@router.get("/demo/{demo_id}")
def get_demo(demo_id: str):
    """One demo item. 404 if absent/malformed."""
    item = service.get_demo(demo_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"demo {demo_id!r} not found")
    return ok(data=item.model_dump())


@router.put("/demo/{demo_id}")
def update_demo(demo_id: str, body: DemoInput):
    """Update a demo item (preserve createdAt). 404 if absent."""
    item = service.update_demo(demo_id, body)
    if item is None:
        raise HTTPException(status_code=404, detail=f"demo {demo_id!r} not found")
    return ok(data=item.model_dump())


@router.delete("/demo/{demo_id}")
def delete_demo(demo_id: str):
    """Delete a demo item (one git commit). 404 if absent."""
    if not service.delete_demo(demo_id):
        raise HTTPException(status_code=404, detail=f"demo {demo_id!r} not found")
    return ok(data={"deleted": demo_id})


MODULE = BaseModule(name="career", router=router)
