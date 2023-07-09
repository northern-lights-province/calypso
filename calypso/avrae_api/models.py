from pydantic import BaseModel


class Gvar(BaseModel):
    owner: int
    key: str
    owner_name: str
    value: str
    editors: list[int]


class Signature(BaseModel):
    message_id: int
    channel_id: int
    author_id: int
    timestamp: float
    workshop_collection_id: str | None = None
    scope: str
    user_data: int
    guild_id: int | None = None
