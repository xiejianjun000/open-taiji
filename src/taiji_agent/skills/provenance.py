"""技能来源追踪 — ContextVar 标记技能写入来源

区分后台自改进（background_review）和前台用户导向的写入。
馆长（Curator）只管理后台自改进创建的技能。

使用:
    from taiji_agent.skills.provenance import (
        set_write_origin, reset_write_origin,
        get_write_origin, is_background_review,
    )

    token = set_write_origin("background_review")
    try:
        ...  # 工具在此运行
    finally:
        reset_write_origin(token)

    # 在工具内部:
    if is_background_review():
        mark_agent_created(skill_name)
"""
import contextvars

_write_origin: contextvars.ContextVar[str] = contextvars.ContextVar(
    "skill_write_origin", default="foreground"
)

BACKGROUND_REVIEW = "background_review"


def set_write_origin(origin: str) -> contextvars.Token[str]:
    return _write_origin.set(origin or "foreground")


def reset_write_origin(token: contextvars.Token[str]) -> None:
    _write_origin.reset(token)


def get_write_origin() -> str:
    return _write_origin.get()


def is_background_review() -> bool:
    return get_write_origin() == BACKGROUND_REVIEW
