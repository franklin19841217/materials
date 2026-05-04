"""啟動入口：python start.py"""
import os

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
