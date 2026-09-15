"""SQLite 스키마 초기화, 간단한 마이그레이션과 데모 fixture 관리."""

from __future__ import annotations

import json

from .core import DB_PATH, GATEWAY, db, now
from .react_tools import DEFAULT_REACT_AGENT_IDS, DEFAULT_REACT_AGENT_META, default_react_definition
from .connectors import hydrate_react_definition
from .workflow_service import graph


def initialize_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as c:
        # CREATE IF NOT EXISTS를 사용해 기존 사용자의 데이터는 유지한다.
        c.executescript("""
        CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY, name TEXT, role TEXT, area TEXT, owner TEXT,
          lifecycle TEXT, version INTEGER, definition TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS agent_versions(agent_id TEXT, version INTEGER, definition TEXT, published_at TEXT,
          PRIMARY KEY(agent_id,version));
        CREATE TABLE IF NOT EXISTS executions(id TEXT PRIMARY KEY, agent_id TEXT, agent_name TEXT, role TEXT,
          area TEXT, version INTEGER, status TEXT, trigger_type TEXT, trigger TEXT, snapshot TEXT,
          initiating_context TEXT, source_report_id TEXT, child_execution_id TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS trace(id INTEGER PRIMARY KEY AUTOINCREMENT, execution_id TEXT, node_id TEXT,
          label TEXT, status TEXT, input_summary TEXT, output_summary TEXT, started_at TEXT, ended_at TEXT);
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, execution_id TEXT UNIQUE, reviewer_role TEXT,
          status TEXT, draft TEXT, original_draft TEXT, decision TEXT, actor TEXT, comment TEXT, decided_at TEXT);
        CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, kind TEXT, title TEXT, area TEXT, threat TEXT,
          content TEXT, source_execution_id TEXT UNIQUE, approved_by TEXT, approved_at TEXT,
          source_report_ids TEXT, fixture INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS report_events(id TEXT PRIMARY KEY, report_id TEXT UNIQUE, status TEXT,
          child_execution_id TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY, role TEXT, title TEXT, body TEXT,
          execution_id TEXT, created_at TEXT, read_at TEXT);
        CREATE TABLE IF NOT EXISTS sensor_events(id TEXT PRIMARY KEY, sensor_id TEXT, type TEXT, area TEXT,
          object_count INTEGER, confidence REAL, execution_id TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS react_agents(id TEXT PRIMARY KEY, name TEXT, description TEXT, role TEXT, owner TEXT,
          lifecycle TEXT, version INTEGER, definition TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS react_agent_runs(id TEXT PRIMARY KEY, react_agent_id TEXT, user_id TEXT, status TEXT,
          prompt TEXT, answer TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS react_chat_sessions(id TEXT PRIMARY KEY, react_agent_id TEXT, user_id TEXT,
          title TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS react_agent_events(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, event_type TEXT,
          title TEXT, content TEXT, tool_name TEXT, payload TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS leave_requests(id TEXT PRIMARY KEY, service_number TEXT, member_name TEXT, unit TEXT,
          leave_type TEXT, start_date TEXT, end_date TEXT, requested_days INTEGER, remaining_days INTEGER,
          unit_event_summary TEXT, status TEXT, execution_id TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS intranet_registrations(id TEXT PRIMARY KEY, leave_request_id TEXT UNIQUE,
          status TEXT, summary TEXT, registered_by TEXT, registered_at TEXT);
        CREATE TABLE IF NOT EXISTS personnel_movements(id TEXT PRIMARY KEY, member_name TEXT, unit TEXT,
          movement_type TEXT, start_at TEXT, end_at TEXT, status TEXT, reason TEXT);
        """)
        # 별도 마이그레이션 도구 대신 필요한 컬럼만 안전하게 보강한다.
        notification_columns={column["name"] for column in c.execute("PRAGMA table_info(notifications)")}
        if "read_at" not in notification_columns:
            c.execute("ALTER TABLE notifications ADD COLUMN read_at TEXT")
        react_run_columns={column["name"] for column in c.execute("PRAGMA table_info(react_agent_runs)")}
        if "session_id" not in react_run_columns:
            c.execute("ALTER TABLE react_agent_runs ADD COLUMN session_id TEXT")
        # 역할별 시스템 기본 에이전트를 하나씩 유지한다. 기존 seed ID는 채팅 기록 보존을 위해 그대로 사용한다.
        default_owners = {
            "ANALYST": "analyst.a12", "STAFF": "staff.ops",
            "COMMANDER": "commander.demo", "ADMIN": "admin.hr01",
        }
        for role, agent_id in DEFAULT_REACT_AGENT_IDS.items():
            meta = DEFAULT_REACT_AGENT_META[role]
            definition = default_react_definition(GATEWAY.model, role)
            timestamp = now()
            c.execute("INSERT OR IGNORE INTO react_agents VALUES(?,?,?,?,?,?,?,?,?)",
                      (agent_id, meta["name"], meta["description"], role, default_owners[role],
                       "PUBLISHED", 1, json.dumps(definition, ensure_ascii=False), timestamp))
            c.execute("UPDATE react_agents SET name=?,description=?,role=?,owner=?,lifecycle='PUBLISHED',"
                      "version=CASE WHEN version<1 THEN 1 ELSE version END,definition=?,updated_at=? WHERE id=?",
                      (meta["name"], meta["description"], role, default_owners[role],
                       json.dumps(definition, ensure_ascii=False), timestamp, agent_id))
        for saved_agent in c.execute("SELECT id,role,definition FROM react_agents").fetchall():
            saved_definition=json.loads(saved_agent["definition"])
            if "require_approval" in saved_definition:
                saved_definition.pop("require_approval",None)
            saved_definition=hydrate_react_definition(saved_definition,saved_agent["role"])
            c.execute("UPDATE react_agents SET definition=? WHERE id=?",(json.dumps(saved_definition,ensure_ascii=False),saved_agent["id"]))
        if not c.execute("SELECT 1 FROM agents").fetchone():
            for agent_id, name, role, area, owner in [
                ("analyst-a12", "파주 감시·위협분석 워크플로우", "ANALYST", "경기도 파주시", "analyst.a12"),
                ("staff-synthesis", "접경지역 상황종합 워크플로우", "STAFF", "접경지역 전체", "staff.ops"),
            ]:
                c.execute("INSERT INTO agents VALUES(?,?,?,?,?,?,?,?,?)", (agent_id, name, role, area, owner,
                          "PUBLISHED", 1, json.dumps(graph(role), ensure_ascii=False), now()))
                c.execute("INSERT OR IGNORE INTO agent_versions VALUES(?,?,?,?)",
                          (agent_id, 1, json.dumps(graph(role), ensure_ascii=False), now()))
        admin_definition=graph("ADMIN")
        c.execute("INSERT OR IGNORE INTO agents VALUES(?,?,?,?,?,?,?,?,?)",
                  ("admin-leave-registration","정기 휴가 검토·등록 워크플로우","ADMIN","제1행정부대","admin.hr01",
                   "PUBLISHED",1,json.dumps(admin_definition,ensure_ascii=False),now()))
        c.execute("INSERT OR IGNORE INTO agent_versions VALUES(?,?,?,?)",
                  ("admin-leave-registration",1,json.dumps(admin_definition,ensure_ascii=False),now()))
        if not c.execute("SELECT 1 FROM personnel_movements").fetchone():
            for movement in [
                ("MOV-001","김민준","본부중대","외출","2026-09-11 17:30","2026-09-11 21:00","승인","개인 용무"),
                ("MOV-002","이준호","본부중대","외박","2026-09-12 09:00","2026-09-13 20:30","승인","가족 행사"),
                ("MOV-003","박서준","지원중대","외출","2026-09-12 13:00","2026-09-12 18:00","대기","개인 용무"),
                ("MOV-004","최도윤","지원중대","외박","2026-09-12 09:00","2026-09-13 20:30","승인","정기 외박"),
                ("MOV-005","정우진","본부중대","외출","2026-09-13 14:00","2026-09-13 19:00","대기","면회"),
            ]:
                c.execute("INSERT INTO personnel_movements VALUES(?,?,?,?,?,?,?,?)",movement)
        if not c.execute("SELECT 1 FROM reports WHERE fixture=1").fetchone():
            for rid, area, threat, content in [
                ("RPT-B07-SEED", "경기도 연천군", "MEDIUM", "연천군 북부에서 반복 이동 징후가 식별되었습니다."),
                ("RPT-C03-SEED", "강원특별자치도 철원군", "LOW", "철원군 일대는 특이 동향 없이 안정적입니다."),
            ]:
                c.execute("INSERT INTO reports VALUES(?,?,?,?,?,?,?,?,?,?,1)",
                          (rid, "REGIONAL", f"{area} 지역 분석 보고", area, threat, content, None,
                           "seed.system", now(), "[]"))
        # 기존 데모 DB의 구조와 사용자 설정은 유지하고 표시용 기본 데이터만 새 명칭으로 이관한다.
        for agent_id, name, area, owner, role in [
            ("analyst-a12", "파주 감시·위협분석 워크플로우", "경기도 파주시", "analyst.a12", "ANALYST"),
            ("staff-synthesis", "접경지역 상황종합 워크플로우", "접경지역 전체", "staff.ops", "STAFF"),
        ]:
            saved = c.execute("SELECT definition FROM agents WHERE id=?", (agent_id,)).fetchone()
            if saved:
                definition = graph(role)
                c.execute("UPDATE agents SET name=?,area=?,owner=?,definition=? WHERE id=?",
                          (name, area, owner, json.dumps(definition, ensure_ascii=False), agent_id))
                current=c.execute("SELECT version,lifecycle FROM agents WHERE id=?",(agent_id,)).fetchone()
                if current and current["lifecycle"]=="PUBLISHED":
                    c.execute("INSERT OR IGNORE INTO agent_versions VALUES(?,?,?,?)",
                              (agent_id,current["version"],json.dumps(definition,ensure_ascii=False),now()))
        c.execute("UPDATE reports SET area='경기도 연천군',title='연천군 위협분석 보고',content='연천군 북부에서 반복 이동 징후가 식별되었습니다.' WHERE id='RPT-B07-SEED'")
        c.execute("UPDATE reports SET area='강원특별자치도 철원군',title='철원군 위협분석 보고',content='철원군 일대는 특이 동향 없이 안정적입니다.' WHERE id='RPT-C03-SEED'")
        c.execute("UPDATE reports SET area='경기도 파주시',title=replace(title,'A-12 지역','파주시') WHERE area='A-12'")
        c.execute("UPDATE executions SET area='경기도 파주시' WHERE area='A-12'")
        c.execute("UPDATE executions SET area='접경지역 전체' WHERE area='ALL'")
