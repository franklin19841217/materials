import os
import json
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from typing import List
from models import LumberItem, OtherItem

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

LUMBER_SHEET = "板材角材"
OTHER_SHEET  = "其他材料"
LUMBER_HEADERS = ["分類", "規格", "廠商", "單位", "單價"]
OTHER_HEADERS  = ["類別", "品名", "規格", "單位", "單價"]

# ── 路徑工具 ────────────────────────────────────────────

def _creds_dir() -> str:
    """回傳 credentials 資料夾的絕對路徑（相對於本檔案的上層）。"""
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "credentials")
    )

def _find_client_secret() -> str:
    """自動找 credentials 資料夾內的 client_secret_*.json，
    若有多個取字母序第一個；找不到才 fallback 到 credentials.json。"""
    explicit = os.getenv("CREDENTIALS_PATH", "")
    if explicit and os.path.exists(explicit):
        return explicit

    d = _creds_dir()
    if os.path.isdir(d):
        candidates = sorted(
            f for f in os.listdir(d)
            if f.startswith("client_secret_") and f.endswith(".json")
        )
        if candidates:
            return os.path.join(d, candidates[0])

    return os.path.join(d, "credentials.json")   # fallback

def _token_path() -> str:
    return os.getenv(
        "TOKEN_PATH",
        os.path.join(_creds_dir(), "token.json")
    )

# ── 記憶體快取（Railway 重啟後重讀環境變數即可）──────────────
_creds_cache: dict = {}   # key: "creds", value: Credentials

# ── 環境變數 token（Railway 部署用）──────────────────────────

def _get_token_from_env() -> Credentials | None:
    """從 GOOGLE_TOKEN_JSON 環境變數讀取 Credentials，失敗回傳 None。"""
    raw = os.getenv("GOOGLE_TOKEN_JSON", "").strip()
    if not raw:
        return None
    try:
        info = json.loads(raw)
        return Credentials.from_authorized_user_info(info, SCOPES)
    except Exception:
        return None

# ── OAuth 核心 ───────────────────────────────────────────

def is_authenticated() -> bool:
    """快速檢查：token 有效（或可刷新）。優先讀環境變數，其次讀檔案。"""
    # 1. 先看記憶體快取
    creds = _creds_cache.get("creds")
    if creds and creds.valid:
        return True

    # 2. 環境變數（Railway）
    creds = _get_token_from_env()
    if creds is None:
        # 3. 本地檔案
        tp = _token_path()
        if not os.path.exists(tp):
            return False
        try:
            creds = Credentials.from_authorized_user_file(tp, SCOPES)
        except Exception:
            return False

    if creds.valid:
        _creds_cache["creds"] = creds
        return True
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _try_save_token(creds)
            _creds_cache["creds"] = creds
            return True
        except Exception:
            pass
    return False

def run_auth_flow() -> None:
    """執行 OAuth 授權（本地開發用）。開啟瀏覽器，完成後存 token.json。
    Railway 雲端不支援此流程，請改用 GOOGLE_TOKEN_JSON 環境變數。"""
    client_secret = _find_client_secret()
    if not os.path.exists(client_secret):
        raise FileNotFoundError(
            f"找不到 OAuth 憑證檔案（搜尋路徑：{_creds_dir()}）\n"
            "請將 Google Cloud Console 下載的 client_secret_*.json 放入 credentials 資料夾。"
        )
    flow  = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
    creds = flow.run_local_server(port=0)
    _try_save_token(creds)
    _creds_cache["creds"] = creds

def _try_save_token(creds: Credentials) -> None:
    """儲存 token.json；雲端環境寫入失敗時靜默略過。"""
    try:
        tp = _token_path()
        os.makedirs(os.path.dirname(tp), exist_ok=True)
        with open(tp, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    except Exception:
        pass   # Railway 唯讀檔案系統，靜默略過

def _get_creds() -> Credentials:
    """取得有效的 Credentials，必要時自動刷新。優先環境變數，其次檔案。"""
    # 記憶體快取
    creds = _creds_cache.get("creds")
    if creds and creds.valid:
        return creds

    # 環境變數
    creds = _get_token_from_env()
    if creds is None:
        tp = _token_path()
        if not os.path.exists(tp):
            raise RuntimeError("尚未完成 Google 授權，請先呼叫 /auth/start")
        creds = Credentials.from_authorized_user_file(tp, SCOPES)

    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _try_save_token(creds)

    _creds_cache["creds"] = creds
    return creds

def _get_client() -> gspread.Client:
    return gspread.authorize(_get_creds())

# ── 試算表操作 ────────────────────────────────────────────

def create_spreadsheet(title: str = "材料資料庫") -> dict:
    """在使用者的 Google Drive 建立新試算表，回傳 id 與 URL。"""
    client = _get_client()
    sh = client.create(title)
    return {
        "spreadsheet_id": sh.id,
        "url": f"https://docs.google.com/spreadsheets/d/{sh.id}/edit",
        "title": title,
    }

def _ensure_worksheet(sh: gspread.Spreadsheet, title: str, headers: list) -> gspread.Worksheet:
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=2000, cols=len(headers) + 2)

    if ws.row_values(1) != headers:
        ws.clear()
        ws.append_row(headers, value_input_option="USER_ENTERED")
    return ws

def load_lumber(spreadsheet_id: str) -> list:
    """從試算表讀取板材角材，回傳 list of dict。"""
    sh = _get_client().open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(LUMBER_SHEET)
    except gspread.WorksheetNotFound:
        return []
    return ws.get_all_records()


def load_other(spreadsheet_id: str) -> list:
    """從試算表讀取其他材料，回傳 list of dict。"""
    sh = _get_client().open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(OTHER_SHEET)
    except gspread.WorksheetNotFound:
        return []
    return ws.get_all_records()


def overwrite_lumber(items: List[LumberItem], spreadsheet_id: str) -> int:
    sh = _get_client().open_by_key(spreadsheet_id)
    ws = _ensure_worksheet(sh, LUMBER_SHEET, LUMBER_HEADERS)
    ws.resize(rows=1)

    rows = [[
        item.category   or "",
        item.spec_label or item.raw_spec or "",
        item.supplier   or "",
        item.unit       or "片",
        item.unit_price if item.unit_price is not None else "",
    ] for item in items]

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)

def overwrite_other(items: List[OtherItem], spreadsheet_id: str) -> int:
    sh = _get_client().open_by_key(spreadsheet_id)
    ws = _ensure_worksheet(sh, OTHER_SHEET, OTHER_HEADERS)
    ws.resize(rows=1)

    rows = [[
        item.category   or "",
        item.name,
        item.spec       or "",
        item.unit       or "",
        item.unit_price if item.unit_price is not None else "",
    ] for item in items]

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)
