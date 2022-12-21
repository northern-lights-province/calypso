import abc
import logging

import aiohttp


class BaseClient(abc.ABC):
    SERVICE_BASE: str = ...
    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, http: aiohttp.ClientSession):
        self.http = http

    async def request(self, method: str, route: str, **kwargs):
        try:
            async with self.http.request(method, f"{self.SERVICE_BASE}{route}", **kwargs) as resp:
                self.logger.debug(f"{method} {self.SERVICE_BASE}{route} returned {resp.status}")
                if not 199 < resp.status < 300:
                    data = await resp.text()
                    self.logger.warning(
                        f"{method} {self.SERVICE_BASE}{route} returned {resp.status} {resp.reason}\n{data}"
                    )
                    raise RuntimeError(f"Request returned an error: {resp.status}: {resp.reason}")
                try:
                    data = await resp.json()
                    self.logger.debug(data)
                except (aiohttp.ContentTypeError, ValueError, TypeError):
                    data = await resp.text()
                    self.logger.warning(
                        f"{method} {self.SERVICE_BASE}{route} response could not be deserialized:\n{data}"
                    )
                    raise RuntimeError(f"Could not deserialize response: {data}")
        except aiohttp.ServerTimeoutError:
            self.logger.warning(f"Request timeout: {method} {self.SERVICE_BASE}{route}")
            raise RuntimeError("Timed out connecting. Please try again in a few minutes.")
        return data

    async def get(self, route: str, **kwargs):
        return await self.request("GET", route, **kwargs)

    async def post(self, route: str, **kwargs):
        return await self.request("POST", route, **kwargs)
