from pydantic import BaseModel, field_validator, ConfigDict
from typing import List, Optional

class LumberItem(BaseModel):
    model_config = ConfigDict(extra='ignore')   # 忽略前端多送的欄位（如 colorCode）

    id:         str
    category:   Optional[str] = ""
    spec_label: Optional[str] = ""
    raw_spec:   Optional[str] = ""
    thickness:  Optional[str] = None            # 描述字串，如 "18mm"、"5.5分"、"1寸"
    supplier:   Optional[str] = ""
    unit:       Optional[str] = "片"
    unit_price: Optional[float] = None

    @field_validator('unit_price', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        if v == '' or v is None:
            return None
        return v

class OtherItem(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id:         str
    category:   Optional[str] = ""
    name:       str
    spec:       Optional[str] = ""
    unit:       Optional[str] = ""
    unit_price: Optional[float] = None

    @field_validator('unit_price', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        if v == '' or v is None:
            return None
        return v

class SyncLumberRequest(BaseModel):
    items: List[LumberItem]

class SyncOtherRequest(BaseModel):
    items: List[OtherItem]
