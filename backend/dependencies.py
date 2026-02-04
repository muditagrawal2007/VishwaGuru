from fastapi import Request
import httpx
from typing import Optional

# Global shared client reference to be initialized by main app lifespan
SHARED_HTTP_CLIENT: Optional[httpx.AsyncClient] = None

def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    Dependency to get the shared HTTP client from app state.
    """
    return request.app.state.http_client
