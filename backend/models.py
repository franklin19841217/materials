from pydantic import BaseModel
from typing import List, Optional

class LumberItem(BaseModel):
    id:         str
    category:   Optional[str]   = ""   # 分類（夾板／角材…）
    spec_label: Optional[str]   = ""   # 前端計算好的規格文字
    raw_spec:   Optional[str]   = ""   # 匯入時的原始規格
    length:     Optional[float] = None
    width:      Optional[float] = None
    thickness:  Optional[float] = None
    supplier:   Optional[str]   = ""
    unit:       Optional[str]   = "片"
    unit_price: Optional[float] = None

class OtherItem(BaseModel):
    id: str
    category:   Optional[str]   = ""
    name:       str
    spec:       Optional[str]   = ""
    unit:       Optional[str]   = ""
    unit_price: Optional[float] = None

class SyncLumberRequest(BaseModel):
    items: List[LumberItem]

class SyncOtherRequest(BaseModel):
    items: List[OtherItem]
