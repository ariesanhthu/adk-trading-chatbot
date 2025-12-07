"""
MCP Client - Kết nối và giao tiếp với MCP Server qua HTTP.

Sử dụng JSON-RPC over HTTP (streamable-http transport).
FastMCP streamable-http sử dụng SSE format cho response.
"""

import json
import time
from typing import Any, Dict, Optional

import httpx

from agents.config import AgentConfig


class MCPClient:
    """Client để kết nối và gọi MCP Server qua HTTP."""

    # Các endpoint có thể thử
    ENDPOINTS = ["/mcp", "/"]

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Khởi tạo MCP Client.

        Args:
            config: AgentConfig instance (nếu None, sẽ tạo mới)
        """
        self.config = config or AgentConfig()
        self.server_url = self.config.mcp_server_url
        self.timeout = self.config.mcp_timeout
        self.session_id: Optional[str] = None

    def _parse_sse_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse SSE (Server-Sent Events) response từ FastMCP streamable-http.

        Args:
            response_text: Response text từ server

        Returns:
            Parsed JSON dict hoặc None nếu có lỗi
        """
        try:
            # Tìm dòng bắt đầu với "data:"
            lines = response_text.strip().split("\n")
            for line in lines:
                if line.startswith("data: "):
                    json_str = line[6:]  # Bỏ "data: "
                    return json.loads(json_str)
            return None
        except Exception as e:
            print(f"Error parsing SSE response: {e}")
            return None

    def _parse_response(self, response: httpx.Response) -> Optional[Dict[str, Any]]:
        """
        Parse response từ MCP server (có thể là SSE hoặc JSON).

        Args:
            response: HTTP response object

        Returns:
            Parsed dict hoặc None nếu có lỗi
        """
        content_type = response.headers.get("content-type", "").lower()
        if "text/event-stream" in content_type:
            # Response là SSE format
            return self._parse_sse_response(response.text)
        else:
            # Response là JSON thông thường
            try:
                return response.json()
            except json.JSONDecodeError:
                return None

    def initialize_session(self, max_retries: int = 3) -> Optional[str]:
        """
        Khởi tạo MCP session và lấy session ID.

        Có retry logic với exponential backoff để xử lý timeout hoặc lỗi tạm thời.

        Args:
            max_retries: Số lần retry tối đa

        Returns:
            Session ID hoặc None nếu thất bại
        """
        if self.session_id:
            return self.session_id

        # Retry logic với exponential backoff
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    # Gọi initialize method
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {
                                "name": "vnstock-adk-agent",
                                "version": "1.0.0",
                            },
                        },
                        "id": 1,
                    }

                    # Thử các endpoint
                    for endpoint in self.ENDPOINTS:
                        try:
                            url = f"{self.server_url}{endpoint}"
                            headers = {
                                "Content-Type": "application/json",
                                "Accept": "application/json, text/event-stream",
                            }

                            resp = client.post(url, json=payload, headers=headers)

                            if (
                                resp.status_code == 404
                                and endpoint != self.ENDPOINTS[-1]
                            ):
                                continue

                            if resp.status_code != 200:
                                print(f"Initialize failed: HTTP {resp.status_code}")
                                if endpoint != self.ENDPOINTS[-1]:
                                    continue
                                return None

                            # Lấy session ID từ response header
                            session_id = resp.headers.get(
                                "mcp-session-id"
                            ) or resp.headers.get("Mcp-Session-Id")

                            if not session_id:
                                print("Warning: No session ID in initialize response")
                                if endpoint != self.ENDPOINTS[-1]:
                                    continue
                                return None

                            # Parse response
                            result = self._parse_response(resp)

                            if result and "error" in result:
                                error_msg = result["error"].get(
                                    "message", "Unknown error"
                                )
                                print(f"Error initializing MCP session: {error_msg}")
                                return None

                            # Lưu session ID
                            self.session_id = session_id

                            # Gọi initialized notification (theo MCP spec)
                            try:
                                initialized_payload = {
                                    "jsonrpc": "2.0",
                                    "method": "notifications/initialized",
                                    "params": {},
                                }
                                init_headers = headers.copy()
                                init_headers["mcp-session-id"] = session_id
                                client.post(
                                    url, json=initialized_payload, headers=init_headers
                                )
                            except Exception as e:
                                print(
                                    f"Warning: Failed to send initialized notification: {e}"
                                )

                            return session_id

                        except httpx.HTTPStatusError as e:
                            if (
                                e.response.status_code == 404
                                and endpoint != self.ENDPOINTS[-1]
                            ):
                                continue
                            if attempt < max_retries - 1:
                                wait_time = 2**attempt
                                print(
                                    f"Error initializing session: HTTP {e.response.status_code}. "
                                    f"Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                                )
                                time.sleep(wait_time)
                                continue
                            print(
                                f"Error initializing session: HTTP {e.response.status_code}"
                            )
                            return None

            except (
                httpx.TimeoutException,
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
            ) as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    print(
                        f"MCP server timeout. Retrying in {wait_time}s... "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                print(
                    f"Error initializing MCP session: Timeout after {max_retries} attempts"
                )
                print(
                    f"Note: MCP server at {self.server_url} may be slow "
                    "(cold start) or unavailable"
                )
                return None
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    print(
                        f"Error initializing MCP session: {e}. "
                        f"Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                print(f"Error initializing MCP session: {e}")
                return None

        return None

    def call_jsonrpc(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        request_id: int = 1,
    ) -> Dict[str, Any]:
        """
        Gọi MCP server qua JSON-RPC over HTTP.

        Args:
            method: Tên method JSON-RPC
            params: Parameters cho method
            request_id: Request ID

        Returns:
            Response từ server hoặc dict chứa error
        """
        # Đảm bảo session đã được initialize
        if not self.session_id:
            session_result = self.initialize_session()
            if not session_result:
                return {
                    "error": "Failed to initialize MCP session",
                    "method": method,
                }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "method": method,
                    "id": request_id,
                }
                if params:
                    payload["params"] = params

                # Thử các endpoint
                for endpoint in self.ENDPOINTS:
                    try:
                        url = f"{self.server_url}{endpoint}"
                        headers = {
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream",
                            "mcp-session-id": self.session_id,
                        }

                        resp = client.post(url, json=payload, headers=headers)

                        if resp.status_code == 404 and endpoint != self.ENDPOINTS[-1]:
                            continue

                        resp.raise_for_status()

                        # Parse response
                        result = self._parse_response(resp)

                        if not result:
                            return {
                                "error": "Failed to parse response",
                                "method": method,
                            }

                        if "error" in result:
                            error_obj = result["error"]
                            # Error có thể là dict hoặc string
                            if isinstance(error_obj, dict):
                                error_msg = error_obj.get("message", str(error_obj))
                                error_code = error_obj.get("code")
                            else:
                                error_msg = str(error_obj)
                                error_code = None
                            return {
                                "error": error_msg,
                                "code": error_code,
                                "method": method,
                            }

                        return result.get("result", result)

                    except httpx.HTTPStatusError as e:
                        if (
                            e.response.status_code == 404
                            and endpoint != self.ENDPOINTS[-1]
                        ):
                            continue
                        return {
                            "error": f"HTTP {e.response.status_code}: {e.response.text}",
                            "method": method,
                            "endpoint": endpoint,
                        }

                return {
                    "error": "Failed to connect to MCP server",
                    "method": method,
                    "note": f"Tried endpoints: {self.ENDPOINTS}",
                }

        except Exception as e:
            return {
                "error": str(e),
                "method": method,
                "note": f"Failed to call MCP server at {self.server_url}",
            }
