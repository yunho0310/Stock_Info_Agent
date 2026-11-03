"""
중복 제거 저장소 (SQLite).

이미 요약해서 보낸 공시(rcept_no)를 기록해 두고,
다음 실행 때 '새 공시'만 골라냅니다.

→ 나중에 자산관리 API 서버의 MySQL 로 옮기기 쉽게,
   인터페이스(filter_new / mark_sent)만 똑같이 유지하면 됩니다.
"""
from __future__ import annotations
import sqlite3
from contextlib import closing

import config


def _conn():
    return sqlite3.connect(config.DB_PATH)


def init_db():
    with closing(_conn()) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS seen_disclosures (
                rcept_no   TEXT PRIMARY KEY,
                corp_name  TEXT,
                report_nm  TEXT,
                rcept_dt   TEXT,
                sent_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.commit()


def filter_new(items: list[dict]) -> list[dict]:
    """아직 기록에 없는(=새) 공시만 반환."""
    if not items:
        return []
    with closing(_conn()) as c:
        seen = {r[0] for r in c.execute("SELECT rcept_no FROM seen_disclosures")}
    return [it for it in items if it["rcept_no"] not in seen]


def mark_sent(items: list[dict]):
    """전송 완료한 공시를 기록."""
    if not items:
        return
    with closing(_conn()) as c:
        c.executemany(
            "INSERT OR IGNORE INTO seen_disclosures "
            "(rcept_no, corp_name, report_nm, rcept_dt) VALUES (?,?,?,?)",
            [(it["rcept_no"], it["corp_name"], it["report_nm"], it["rcept_dt"]) for it in items],
        )
        c.commit()
