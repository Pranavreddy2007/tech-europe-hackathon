import re

from sqlalchemy import select, text

from ..db import AgentAction, Knowledge, aware, engine, session_scope
from ..schemas import ActionLogged, Correction, KnowledgeResult, KnowledgeStored, QueryResult, ToolError

_WRITE_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|ATTACH|DETACH|PRAGMA|COPY|VACUUM)\b",
    re.IGNORECASE,
)


async def get_knowledge(term: str) -> KnowledgeResult:
    async with session_scope() as s:
        rows = (
            await s.scalars(
                select(Knowledge).where(Knowledge.term.ilike(f"%{term}%")).order_by(Knowledge.created_at.desc())
            )
        ).all()
    if not rows:
        return KnowledgeResult(found=False, term=term, message=f'No team corrections found for "{term}".')
    return KnowledgeResult(
        found=True,
        term=term,
        corrections=[
            Correction(definition=r.definition, source_user=r.source_user, created_at=aware(r.created_at))
            for r in rows
        ],
    )


async def store_knowledge(term: str, definition: str, source_user: str) -> KnowledgeStored:
    async with session_scope() as s:
        s.add(Knowledge(term=term, definition=definition, source_user=source_user))
    return KnowledgeStored(stored=True, term=term, definition=definition, source_user=source_user)


async def log_action(
    action_type: str, trigger: str, reasoning: str, message_sent: str | None, tools_used: list | None = None
) -> ActionLogged:
    async with session_scope() as s:
        action = AgentAction(
            action_type=action_type,
            trigger=trigger,
            reasoning=reasoning,
            tools_used=tools_used or [],
            message_sent=message_sent,
        )
        s.add(action)
        await s.flush()
        return ActionLogged(logged=True, id=action.id)


async def query_data(sql: str) -> QueryResult | ToolError:
    """Run agent-written read-only SQL. The statement always runs inside a rolled-back transaction."""
    if _WRITE_SQL.search(sql) or ";" in sql.strip().rstrip(";"):
        return ToolError(error="Only a single SELECT query is allowed. Write operations are forbidden.")
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                result = await conn.execute(text(sql))
                rows = [dict(r._mapping) for r in result.fetchall()]
            finally:
                await trans.rollback()
    except Exception as err:  # surface SQL errors to the agent instead of crashing the loop
        return ToolError(error=f"Query failed: {err}")
    return QueryResult(rows=rows[:50], row_count=len(rows))
