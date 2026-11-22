"""Centralized API Client with retries, rate limiting, logging, and bridge fallback."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional, Tuple
import httpx

logger = logging.getLogger("zepto.api.client")
logger.setLevel(logging.INFO)

BFF_DEFAULT = "https://bff-gateway.zepto.com"
WEB_DEFAULT = "https://www.zepto.com"


class ZeptoApiClient:
    """Centralized HTTP client interacting with Zepto APIs and local fallback."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url or os.environ.get("ZEPTO_API_BASE", BFF_DEFAULT)
        self.web_base = os.environ.get("ZEPTO_WEB_BASE", WEB_DEFAULT)
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "accept": "application/json, text/plain, */*",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "origin": "https://www.zepto.com",
                "referer": "https://www.zepto.com/",
            },
        )

    async def close(self):
        await self.session.aclose()

    async def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth_token: Optional[str] = None,
    ) -> Tuple[int, Any, float]:
        """Perform request with automatic retries, timing, and rate-limit detection."""
        url = path if path.startswith("http") else f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        req_headers = dict(headers or {})
        if auth_token:
            req_headers["session_id"] = auth_token
            req_headers["x-csrf-secret"] = "csrf_sec_auth"

        start_time = time.time()
        last_error = None
        status_code = 500
        response_data: Any = None

        for attempt in range(self.max_retries):
            try:
                response = await self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=req_headers,
                )
                status_code = response.status_code
                execution_time = (time.time() - start_time) * 1000

                # Check rate limits
                if status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2))
                    logger.warning(f"Rate limited on {url}. Backing off for {retry_after}s")
                    await self._sleep(retry_after)
                    continue

                try:
                    response_data = response.json()
                except Exception:
                    response_data = {"text": response.text}

                logger.info(
                    f"API Call {method} {url} -> {status_code} ({execution_time:.1f}ms)"
                )
                return status_code, response_data, execution_time

            except Exception as exc:
                last_error = exc
                logger.error(f"Attempt {attempt+1} failed for {method} {url}: {exc}")
                await self._sleep(1.0 * (attempt + 1))

        execution_time = (time.time() - start_time) * 1000
        return status_code, {"error": str(last_error or "Max retries exceeded")}, execution_time

    async def _sleep(self, seconds: float):
        import asyncio
        await asyncio.sleep(seconds)


# Global singleton client
api_client = ZeptoApiClient()
