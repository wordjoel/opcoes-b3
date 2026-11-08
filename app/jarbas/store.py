"""Persistência do Jarbas no banco (Turso em produção): configurações, conversas e consumo.

Nenhuma chave de API passa por aqui. A conta é de um único proprietário, então as
conversas são dele em qualquer aparelho em que ele entrar.
"""

import json
import uuid
from datetime import datetime, timedelta

from db.client import Database

DEFAULTS = {
    "provider_order": ["openrouter", "gemini", "groq", "custom"],
    "openrouter_model": None,
    "allow_paid": False,
    "daily_limit": 200,
    "retention_days": 90,
    "speak_replies": True,
    "voice_name": None,
    "voice_rate": 1.0,
    "updated_at": None,
}


def read_settings(db: Database) -> dict:
    rows = db.fetch(
        "SELECT provider_order, openrouter_model, allow_paid, daily_limit, retention_days, speak_replies, voice_name, voice_rate, updated_at"
        " FROM jarbas_settings WHERE id = 1"
    )
    if not rows:
        return dict(DEFAULTS)
    order, model, paid, limit, retention, speak, voice, rate, updated = rows[0]
    return {
        "provider_order": [item for item in (order or "").split(",") if item] or DEFAULTS["provider_order"],
        "openrouter_model": model,
        "allow_paid": bool(paid),
        "daily_limit": limit,
        "retention_days": retention,
        "speak_replies": bool(speak),
        "voice_name": voice,
        "voice_rate": rate,
        "updated_at": updated,
    }


def save_settings(db: Database, values: dict, now: datetime) -> dict:
    db.run(
        "INSERT INTO jarbas_settings (id, provider_order, openrouter_model, allow_paid, daily_limit, retention_days, speak_replies, voice_name, voice_rate, updated_at)"
        " VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (id) DO UPDATE SET provider_order = excluded.provider_order, openrouter_model = excluded.openrouter_model,"
        " allow_paid = excluded.allow_paid, daily_limit = excluded.daily_limit, retention_days = excluded.retention_days,"
        " speak_replies = excluded.speak_replies, voice_name = excluded.voice_name, voice_rate = excluded.voice_rate, updated_at = excluded.updated_at",
        (
            ",".join(values["provider_order"]),
            values["openrouter_model"],
            int(values["allow_paid"]),
            values["daily_limit"],
            values["retention_days"],
            int(values["speak_replies"]),
            values["voice_name"],
            values["voice_rate"],
            now.isoformat(),
        ),
    )
    return read_settings(db)


def ensure_conversation(db: Database, identity: str | None, question: str, now: datetime) -> str:
    if identity and db.fetch("SELECT 1 FROM jarbas_conversations WHERE id = ?", (identity,)):
        db.run("UPDATE jarbas_conversations SET updated_at = ? WHERE id = ?", (now.isoformat(), identity))
        return identity
    identity = uuid.uuid4().hex
    title = " ".join(question.split())[:80] or "Conversa"
    db.run(
        "INSERT INTO jarbas_conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (identity, title, now.isoformat(), now.isoformat()),
    )
    return identity


def add_message(
    db: Database,
    conversation: str,
    role: str,
    content: str,
    now: datetime,
    provider: str | None = None,
    model: str | None = None,
    context: dict | None = None,
    tools: list | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    latency_ms: int | None = None,
) -> None:
    db.run(
        "INSERT INTO jarbas_messages (conversation_id, role, content, provider, model, context_json, tools_json, prompt_tokens, completion_tokens, latency_ms, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            conversation,
            role,
            content,
            provider,
            model,
            json.dumps(context, ensure_ascii=False) if context else None,
            json.dumps(tools, ensure_ascii=False) if tools else None,
            prompt_tokens,
            completion_tokens,
            latency_ms,
            now.isoformat(),
        ),
    )


def list_conversations(db: Database, limit: int = 50) -> list[dict]:
    rows = db.fetch(
        "SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id) FROM jarbas_conversations c"
        " LEFT JOIN jarbas_messages m ON m.conversation_id = c.id GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ?",
        (limit,),
    )
    return [{"id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3], "messages": r[4]} for r in rows]


def get_conversation(db: Database, identity: str) -> dict | None:
    head = db.fetch("SELECT id, title, created_at, updated_at FROM jarbas_conversations WHERE id = ?", (identity,))
    if not head:
        return None
    rows = db.fetch(
        "SELECT role, content, provider, model, created_at FROM jarbas_messages WHERE conversation_id = ? ORDER BY id",
        (identity,),
    )
    return {
        "id": head[0][0],
        "title": head[0][1],
        "created_at": head[0][2],
        "updated_at": head[0][3],
        "messages": [{"role": r[0], "content": r[1], "provider": r[2], "model": r[3], "created_at": r[4]} for r in rows],
    }


def history_for_model(db: Database, identity: str, limit: int = 16) -> list[tuple[str, str]]:
    rows = db.fetch(
        "SELECT role, content FROM jarbas_messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?", (identity, limit)
    )
    return list(reversed([(r[0], r[1]) for r in rows]))


def delete_conversation(db: Database, identity: str) -> bool:
    if not db.fetch("SELECT 1 FROM jarbas_conversations WHERE id = ?", (identity,)):
        return False
    db.run("DELETE FROM jarbas_messages WHERE conversation_id = ?", (identity,))
    db.run("DELETE FROM jarbas_conversations WHERE id = ?", (identity,))
    return True


def record_usage(db: Database, day: str, provider: str, model: str, ok: bool, prompt: int | None, completion: int | None) -> None:
    db.run(
        "INSERT INTO jarbas_usage (day, provider, model, requests, failures, prompt_tokens, completion_tokens) VALUES (?, ?, ?, 1, ?, ?, ?)"
        " ON CONFLICT (day, provider, model) DO UPDATE SET requests = requests + 1, failures = failures + excluded.failures,"
        " prompt_tokens = prompt_tokens + excluded.prompt_tokens, completion_tokens = completion_tokens + excluded.completion_tokens",
        (day, provider, model or "-", 0 if ok else 1, prompt or 0, completion or 0),
    )


def questions_on(db: Database, day: str) -> int:
    return db.fetch(
        "SELECT COUNT(*) FROM jarbas_messages WHERE role = 'user' AND created_at >= ? AND created_at < ?",
        (day, day + "￿"),
    )[0][0]


def usage_on(db: Database, day: str) -> dict:
    rows = db.fetch(
        "SELECT provider, model, requests, failures, prompt_tokens, completion_tokens FROM jarbas_usage WHERE day = ? ORDER BY requests DESC",
        (day,),
    )
    models = [
        {"provider": r[0], "model": r[1], "requests": r[2], "failures": r[3], "prompt_tokens": r[4], "completion_tokens": r[5]} for r in rows
    ]
    return {
        "day": day,
        "questions": questions_on(db, day),
        "requests": sum(m["requests"] for m in models),
        "failures": sum(m["failures"] for m in models),
        "tokens": sum(m["prompt_tokens"] + m["completion_tokens"] for m in models),
        "models": models,
    }


def purge(db: Database, retention_days: int, now: datetime) -> None:
    """Apaga mensagens e conversas mais antigas que a retenção configurada."""
    limit = (now - timedelta(days=retention_days)).isoformat()
    db.run("DELETE FROM jarbas_messages WHERE created_at < ?", (limit,))
    db.run(
        "DELETE FROM jarbas_conversations WHERE updated_at < ? AND id NOT IN (SELECT DISTINCT conversation_id FROM jarbas_messages)",
        (limit,),
    )
    db.run("DELETE FROM jarbas_usage WHERE day < ?", (limit[:10],))
