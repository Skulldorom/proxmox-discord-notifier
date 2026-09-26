"""Custom routing primitives."""

from fastapi import HTTPException, Request
from fastapi.routing import APIRoute

from . import config


class LimitedBodyRoute(APIRoute):
    """Read and cap notify request bytes before FastAPI parses JSON."""

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def limited_handler(request: Request):
            limit = config.settings.max_request_bytes
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > limit:
                    raise HTTPException(status_code=413, detail="Request body too large")
            request._body = bytes(body)
            return await original_handler(request)

        return limited_handler
