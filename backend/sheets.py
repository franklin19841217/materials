import os
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

# ── OAuth 核心 ───────────────────────────────────────────

def is_authenticated() -> bool:
    """快速檢查：token.json 存在且有效（或可刷新）。"""
    tp = _token_path()
    if not os.path.exists(tp):
        return False
    try:
        creds = Credentials.from_authorized_user_file(tp, SCOPES)
        if creds.valid:
            return True
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds)
            return True
    except Exception:
        pass
    return False

def run_auth_flow() -> None:
    """執行 OAuth 授權（首次或 token 失效時）。開啟瀏覽器，完成後存 token.json。"""
    client_secret = _find_client_secret()
    if not os.path.exists(client_secret):
        raise FileNotFoundError(
            f"找不到 OAuth 憑證檔案（搜尋路徑：{_creds_dir()}）\n"
            "請將 Google Cloud Console 下載的 client_secret_*.json 放入 credentials 資料夾。"
        )
    flow  = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)

def _save_token(creds: Credentials) -> None:
    tp = _token_path()
    os.makedirs(os.path.dirname(tp), exist_ok=True)
    with open(tp, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

def _get_creds() -> Credentials:
    """取得有效的 Credentials，必要時自動刷新。"""
    tp = _token_path()
    if not os.path.exists(tp):
        raise RuntimeError("尚未完成 Google 授權，請先呼叫 /auth/start")

    creds = Credentials.from_authorized_user_file(tp, SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
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
