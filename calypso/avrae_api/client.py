import aiohttp

from calypso.utils.httpclient import BaseClient
from .models import Gvar


class AvraeClient(BaseClient):
    SERVICE_BASE = "https://api.avrae.io"

    def __init__(self, http: aiohttp.ClientSession, api_key: str):
        super().__init__(http)
        self.api_key = api_key

    async def request(self, method: str, route: str, headers=None, **kwargs):
        if headers is None:
            headers = {}
        headers["Authorization"] = self.api_key
        return await super().request(method, route, headers=headers, **kwargs)

    async def get_gvar(self, gvar_id: str) -> Gvar:
        data = await self.get(f"/gvars/{gvar_id}")
        return Gvar.parse_obj(data)

    async def set_gvar(self, gvar_id: str, value: str) -> str:
        return await self.post(f"/gvars/{gvar_id}", json={"value": value})
