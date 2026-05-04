"""Railway 部署入口：讓根目錄可以找到 backend/ 底下的模組。"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from dotenv import load_dotenv
load_dotenv()

from main import app  # noqa: F401 – uvicorn 需要 app 這個名稱
