from pydantic import BaseModel


class Gvar(BaseModel):
    owner: int
    key: str
    owner_name: str
    value: str
    editors: list[int]
