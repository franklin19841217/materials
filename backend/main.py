from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from models import SyncLumberRequest, SyncOtherRequest
import sheets
import os

app = FastAPI(title="材料資料庫")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "https://franklin19841217.github.io"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "docs"))
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ── 靜態頁面 ─────────────────────────────────────────────

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ── OAuth 授權 ────────────────────────────────────────────

@app.get("/auth/status")
def auth_status():
    """回傳目前是否已完成 Google 授權。"""
    return {"authenticated": sheets.is_authenticated()}


@app.post("/auth/start")
def auth_start():
    """觸發 OAuth 流程（開啟瀏覽器）。已授權則直接回傳成功。"""
    if sheets.is_authenticated():
        return {"success": True, "message": "已授權，無需重新登入"}
    try:
        sheets.run_auth_flow()
        return {"success": True, "message": "授權成功"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"授權失敗：{e}")


# ── 試算表管理 ────────────────────────────────────────────

class CreateSheetRequest(BaseModel):
    title: str = "材料資料庫"

@app.post("/sheets/create")
def sheets_create(req: CreateSheetRequest = CreateSheetRequest()):
    """在使用者 Google Drive 建立新試算表，回傳 spreadsheet_id 和 URL。"""
    if not sheets.is_authenticated():
        raise HTTPException(status_code=401, detail="請先完成 Google 授權（/auth/start）")
    try:
        result = sheets.create_spreadsheet(req.title)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 資料同步 ──────────────────────────────────────────────

def _require_auth_and_id(spreadsheet_id: str):
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="請先填入 Spreadsheet ID")
    if not sheets.is_authenticated():
        raise HTTPException(status_code=401, detail="請先完成 Google 授權")


@app.post("/sync/lumber")
def sync_lumber(req: SyncLumberRequest, spreadsheet_id: str):
    _require_auth_and_id(spreadsheet_id)
    try:
        count = sheets.overwrite_lumber(req.items, spreadsheet_id)
        return {"success": True, "written": count, "sheet": sheets.LUMBER_SHEET}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync/other")
def sync_other(req: SyncOtherRequest, spreadsheet_id: str):
    _require_auth_and_id(spreadsheet_id)
    try:
        count = sheets.overwrite_other(req.items, spreadsheet_id)
        return {"success": True, "written": count, "sheet": sheets.OTHER_SHEET}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
