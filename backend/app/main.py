"""FastAPI 앱을 생성하고 기능별 라우터를 조립한다."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core import GATEWAY, db, now, row, session_for, uid
from .database import initialize_database
from .react_agent import create_react_router
from .view_api import router as view_router
from .workflow_api import router as workflow_router


# 개발 서버를 바로 실행해도 필요한 스키마와 데모 데이터가 준비되게 한다.
initialize_database()

app = FastAPI(title="Defense Workflow Builder Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(view_router)
app.include_router(workflow_router)
app.include_router(create_react_router(db=db, deserialize=row, session_for=session_for, gateway=GATEWAY, now=now, uid=uid))
