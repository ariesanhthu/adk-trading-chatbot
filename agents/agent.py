"""
VNStock Agent sử dụng MCP tools từ VNStock MCP Server qua HTTP.

Sử dụng JSON-RPC over HTTP (streamable-http transport).
FastMCP streamable-http sử dụng SSE format cho response.

Cấu hình MCP server được đọc từ configs/mcp_config.yaml.
Có thể override bằng biến môi trường MCP_SERVER_URL và MCP_TIMEOUT.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx
import yaml
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv

# Load biến môi trường (GOOGLE_API_KEY, v.v.) từ .env nếu có
load_dotenv()

# Load cấu hình MCP từ configs/mcp_config.yaml
_CONFIG_DIR = Path(__file__).parent.parent / "configs"
_CONFIG_FILE = _CONFIG_DIR / "mcp_config.yaml"


def _load_mcp_config() -> Dict[str, Any]:
    """Load cấu hình MCP từ configs/mcp_config.yaml."""
    try:
        if _CONFIG_FILE.exists():
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("mcp_server", {})
    except Exception as e:
        print(f"Warning: Failed to load config from {_CONFIG_FILE}: {e}")
    return {}


# Load config
_mcp_config = _load_mcp_config()

# MCP Server URL - ưu tiên: environment variable > config file > default
MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    _mcp_config.get("url", "https://mcp-server-vietnam-stock-trading.onrender.com"),
)
# Tăng timeout cho Render.com (free tier thường chậm, cần thời gian cold start)
MCP_TIMEOUT = float(os.getenv("MCP_TIMEOUT", str(_mcp_config.get("timeout", 60.0))))

# Session ID cho MCP server (sẽ được lấy sau khi initialize)
_mcp_session_id: Optional[str] = None


def _parse_sse_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse SSE (Server-Sent Events) response từ FastMCP streamable-http."""
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


def _initialize_mcp_session(max_retries: int = 3) -> Optional[str]:
    """
    Khởi tạo MCP session và lấy session ID từ FastMCP streamable-http.
    Có retry logic để xử lý timeout hoặc lỗi tạm thời.
    """
    global _mcp_session_id

    if _mcp_session_id:
        return _mcp_session_id

    # Retry logic với exponential backoff
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=MCP_TIMEOUT) as client:
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

                endpoints_to_try = ["/mcp", "/"]
                for endpoint in endpoints_to_try:
                    try:
                        url = f"{MCP_SERVER_URL}{endpoint}"
                        headers = {
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream",
                        }

                        resp = client.post(url, json=payload, headers=headers)

                        if resp.status_code == 404 and endpoint != endpoints_to_try[-1]:
                            continue

                        if resp.status_code != 200:
                            print(f"Initialize failed: HTTP {resp.status_code}")
                            if endpoint != endpoints_to_try[-1]:
                                continue
                            return None

                        # Lấy session ID từ response header (FastMCP trả về trong mcp-session-id)
                        session_id = resp.headers.get(
                            "mcp-session-id"
                        ) or resp.headers.get("Mcp-Session-Id")

                        if not session_id:
                            print("Warning: No session ID in initialize response")
                            if endpoint != endpoints_to_try[-1]:
                                continue
                            return None

                        # Parse SSE response
                        content_type = resp.headers.get("content-type", "").lower()
                        if "text/event-stream" in content_type:
                            # Response là SSE format
                            result = _parse_sse_response(resp.text)
                        else:
                            # Response là JSON thông thường
                            try:
                                result = resp.json()
                            except json.JSONDecodeError:
                                result = None

                        if result and "error" in result:
                            error_msg = result["error"].get("message", "Unknown error")
                            print(f"Error initializing MCP session: {error_msg}")
                            return None

                        # Lưu session ID
                        _mcp_session_id = session_id
                        # print(f"MCP session initialized: {session_id[:8]}...")

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
                            and endpoint != endpoints_to_try[-1]
                        ):
                            continue
                        if attempt < max_retries - 1:
                            wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                            print(
                                f"Error initializing session: HTTP {e.response.status_code}. Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                            )
                            import time

                            time.sleep(wait_time)
                            continue
                        print(
                            f"Error initializing session: HTTP {e.response.status_code}"
                        )
                        return None

        except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            if attempt < max_retries - 1:
                wait_time = 2**attempt
                print(
                    f"MCP server timeout. Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                )
                import time

                time.sleep(wait_time)
                continue
            print(
                f"Error initializing MCP session: Timeout after {max_retries} attempts"
            )
            print(
                f"Note: MCP server at {MCP_SERVER_URL} may be slow (cold start) or unavailable"
            )
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2**attempt
                print(
                    f"Error initializing MCP session: {e}. Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                )
                import time

                time.sleep(wait_time)
                continue
            print(f"Error initializing MCP session: {e}")
            return None

    return None


def _call_mcp_jsonrpc(
    method: str, params: Optional[Dict[str, Any]] = None, request_id: int = 1
) -> Dict[str, Any]:
    """Gọi MCP server qua JSON-RPC over HTTP (streamable-http transport)."""
    global _mcp_session_id

    # Đảm bảo session đã được initialize
    if not _mcp_session_id:
        session_result = _initialize_mcp_session()
        if not session_result:
            return {
                "error": "Failed to initialize MCP session",
                "method": method,
            }

    try:
        with httpx.Client(timeout=MCP_TIMEOUT) as client:
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "id": request_id,
            }
            if params:
                payload["params"] = params

            # Thử các endpoint có thể có
            endpoints_to_try = ["/mcp", "/"]
            for endpoint in endpoints_to_try:
                try:
                    url = f"{MCP_SERVER_URL}{endpoint}"
                    headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "mcp-session-id": _mcp_session_id,  # FastMCP yêu cầu session ID trong header
                    }

                    resp = client.post(url, json=payload, headers=headers)

                    if resp.status_code == 404 and endpoint != endpoints_to_try[-1]:
                        continue

                    resp.raise_for_status()

                    # Parse response (có thể là SSE hoặc JSON)
                    content_type = resp.headers.get("content-type", "").lower()
                    if "text/event-stream" in content_type:
                        # Response là SSE format
                        result = _parse_sse_response(resp.text)
                    else:
                        # Response là JSON thông thường
                        try:
                            result = resp.json()
                        except json.JSONDecodeError:
                            return {
                                "error": "Invalid JSON response",
                                "method": method,
                                "response": resp.text[:200],
                            }

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
                        and endpoint != endpoints_to_try[-1]
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
                "note": f"Tried endpoints: {endpoints_to_try}",
            }

    except Exception as e:
        return {
            "error": str(e),
            "method": method,
            "note": f"Failed to call MCP server at {MCP_SERVER_URL}",
        }


def _process_arguments(
    tool_name: str, properties: Dict, tool_param_mapping: Dict, **kwargs
):
    """Process và validate arguments từ kwargs."""
    processed_kwargs = {}

    # Áp dụng parameter mapping nếu có
    normalized_kwargs = {}
    for key, value in kwargs.items():
        # Kiểm tra xem có mapping không
        if key in tool_param_mapping:
            normalized_key = tool_param_mapping[key]
            normalized_kwargs[normalized_key] = value
        else:
            normalized_kwargs[key] = value

    # Xử lý từng parameter
    for param_name, param_value in normalized_kwargs.items():
        if param_name not in properties:
            # Nếu tham số không có trong schema, giữ nguyên (có thể là optional)
            processed_kwargs[param_name] = param_value
            continue

        param_schema = properties[param_name]
        param_type = param_schema.get("type")

        # Xử lý đặc biệt cho get_price_board: symbols phải là list
        if tool_name == "get_price_board" and param_name == "symbols":
            if isinstance(param_value, str):
                # Nếu là string, convert thành list
                processed_kwargs[param_name] = [param_value]
            elif isinstance(param_value, list):
                processed_kwargs[param_name] = param_value
            else:
                # Nếu là giá trị khác, thử convert thành list
                processed_kwargs[param_name] = [str(param_value)]
        # Xử lý array/list types
        elif param_type == "array" or (
            isinstance(param_type, list) and "array" in param_type
        ):
            if isinstance(param_value, str):
                # Nếu là string nhưng schema yêu cầu array, convert thành list
                processed_kwargs[param_name] = [param_value]
            elif isinstance(param_value, list):
                processed_kwargs[param_name] = param_value
            else:
                # Nếu là giá trị khác, thử convert thành list
                processed_kwargs[param_name] = [param_value]
        # Xử lý string types: nếu tool cần string nhưng nhận list, lấy phần tử đầu tiên
        elif param_type == "string":
            # Giữ None nếu giá trị là None (không convert thành string "None")
            if param_value is None:
                processed_kwargs[param_name] = None
            elif isinstance(param_value, list):
                # Nếu là list nhưng schema yêu cầu string, lấy phần tử đầu tiên
                if len(param_value) > 0:
                    processed_kwargs[param_name] = str(param_value[0])
                else:
                    processed_kwargs[param_name] = ""
            else:
                # Convert sang string nếu cần
                processed_kwargs[param_name] = str(param_value)
        else:
            # Giữ nguyên giá trị cho các type khác
            processed_kwargs[param_name] = param_value

    return processed_kwargs


def _create_mcp_tool_function(tool_name: str, tool_schema: Dict[str, Any]):
    """Tạo function tool từ MCP tool schema."""
    description = tool_schema.get("description", f"MCP tool: {tool_name}")
    input_schema = tool_schema.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    # Mapping các parameter names phổ biến (LLM có thể dùng tên khác)
    # Áp dụng cho tất cả tools: nếu tool cần "symbol" (số ít) nhưng LLM truyền "symbols" (số nhiều), map lại
    # Ngược lại, nếu tool cần "symbols" (số nhiều) nhưng LLM truyền "symbol" (số ít), map lại
    tool_param_mapping = {}

    # Kiểm tra xem tool có parameter "symbol" hay "symbols"
    has_symbols = "symbols" in properties
    has_symbol = "symbol" in properties

    if has_symbols:
        # Tool cần "symbols" (list), map các biến thể thành "symbols"
        tool_param_mapping = {
            "symbol": "symbols",  # LLM có thể dùng "symbol" (số ít)
            "symbol_list": "symbols",
            "stocks": "symbols",
            "stock": "symbols",
        }
    elif has_symbol:
        # Tool cần "symbol" (string), map các biến thể thành "symbol"
        tool_param_mapping = {
            "symbols": "symbol",  # LLM có thể dùng "symbols" (số nhiều)
            "symbol_list": "symbol",
            "stocks": "symbol",
            "stock": "symbol",
        }

    # Mapping cụ thể cho từng tool (override nếu cần)
    specific_mappings = {
        "get_price_board": {
            "symbol": "symbols",
            "symbol_list": "symbols",
            "stocks": "symbols",
            "stock": "symbols",
        },
    }
    if tool_name in specific_mappings:
        tool_param_mapping = specific_mappings[tool_name]

    # Tạo docstring chi tiết từ schema để ADK hiểu được parameters
    docstring_parts = [description or f"MCP tool: {tool_name}", "", "Parameters:"]
    for param_name, param_schema in properties.items():
        param_type = param_schema.get("type", "Any")
        param_desc = param_schema.get("description", "")
        is_required = param_name in required
        default = param_schema.get("default")

        param_line = f"  {param_name} ({param_type})"
        if not is_required and default is not None:
            param_line += f" = {default}"
        elif not is_required:
            param_line += " (optional)"
        if param_desc:
            param_line += f": {param_desc}"
        docstring_parts.append(param_line)

    full_docstring = "\n".join(docstring_parts)

    # Tạo function signature từ properties
    # Xây dựng parameter list cho function signature
    param_signatures = []
    param_defaults = {}

    for param_name, param_schema in properties.items():
        param_type = param_schema.get("type", "Any")
        default = param_schema.get("default")
        is_required = param_name in required

        # Tạo type annotation string
        if param_type == "array":
            # FIX: Gemini API yêu cầu List[item_type] thay vì list
            items_schema = param_schema.get("items", {})
            items_type = items_schema.get("type", "str")
            if items_type == "string":
                type_annotation = "List[str]"
            elif items_type == "integer":
                type_annotation = "List[int]"
            elif items_type == "number":
                type_annotation = "List[float]"
            else:
                type_annotation = "List[Any]"
        elif param_type == "string":
            type_annotation = "str"
        elif param_type == "integer":
            type_annotation = "int"
        elif param_type == "number":
            type_annotation = "float"
        elif param_type == "boolean":
            type_annotation = "bool"
        else:
            type_annotation = "Any"

        if is_required and default is None:
            # Required parameter, không có default
            param_signatures.append(f"{param_name}: {type_annotation}")
        else:
            # Optional parameter với default
            if default is not None:
                if isinstance(default, str):
                    default_str = f'"{default}"'
                else:
                    default_str = str(default)
                param_signatures.append(
                    f"{param_name}: {type_annotation} = {default_str}"
                )
            else:
                # Optional nhưng không có default value, dùng Optional[type] = None
                # ADK yêu cầu Optional[type] thay vì type = None
                param_signatures.append(
                    f"{param_name}: Optional[{type_annotation}] = None"
                )

    # Tạo function với signature rõ ràng bằng exec
    # Đây là cách duy nhất để ADK có thể parse được parameters
    import inspect

    # Build function body
    func_body_lines = [
        f'    """{full_docstring}"""',
        "    # Collect arguments",
        "    import inspect as _inspect",
        "    frame = _inspect.currentframe()",
        "    args_info = _inspect.getargvalues(frame)",
        "    kwargs = {}",
        "    for arg_name in args_info.args:",
        "        if arg_name in args_info.locals:",
        "            kwargs[arg_name] = args_info.locals[arg_name]",
        "",
        f"    # Process arguments với tool_name='{tool_name}'",
        f"    _tool_name = '{tool_name}'",
        f"    _properties = {properties}",
        f"    _tool_param_mapping = {tool_param_mapping}",
        "",
        "    # Process arguments",
        "    processed_kwargs = _process_arguments_func(_tool_name, _properties, _tool_param_mapping, **kwargs)",
        "",
        "    # Debug log",
        "    print(f'[DEBUG] {_tool_name} called with kwargs: {kwargs}')",
        "    print(f'[DEBUG] {_tool_name} processed to: {processed_kwargs}')",
        "",
        "    # Call MCP server",
        "    result = _call_mcp_jsonrpc_func(",
        '        method="tools/call",',
        "        params={'name': _tool_name, 'arguments': processed_kwargs},",
        "    )",
        "",
        "    # Kiểm tra lỗi - có thể là dict với key 'error' hoặc string error message",
        "    if isinstance(result, dict):",
        "        if 'error' in result:",
        "            error_msg = result.get('error', 'Unknown error')",
        "            # Nếu error là dict, lấy message",
        "            if isinstance(error_msg, dict):",
        "                error_msg = error_msg.get('message', str(error_msg))",
        "            print(f'[ERROR] {_tool_name} failed: {error_msg}')",
        "            print(f'[ERROR] Processed arguments: {processed_kwargs}')",
        "            return {",
        "                'error': str(error_msg),",
        "                'tool': _tool_name,",
        "                'code': result.get('code'),",
        "            }",
        "    elif isinstance(result, str):",
        "        # Kiểm tra nếu result là string chứa error",
        "        if 'error' in result.lower() or 'failed' in result.lower() or len(result.strip()) == 0:",
        "            print(f'[ERROR] {_tool_name} returned error/empty string: {result[:100]}')",
        "            return {",
        "                'error': result if result.strip() else 'Empty response',",
        "                'tool': _tool_name,",
        "            }",
        "",
        "    # Trả về content nếu có",
        "    if 'content' in result:",
        "        content = result['content']",
        "        if isinstance(content, list):",
        "            texts = []",
        "            for item in content:",
        "                if isinstance(item, dict):",
        "                    if 'text' in item:",
        "                        texts.append(item['text'])",
        "                    elif 'type' in item and item.get('type') == 'text':",
        "                        texts.append(item.get('text', ''))",
        "                elif isinstance(item, str):",
        "                    texts.append(item)",
        "            if texts:",
        "                # Nếu chỉ có 1 text item, trả về trực tiếp",
        "                if len(texts) == 1:",
        "                    return texts[0]",
        "                return '\\n'.join(texts)",
        "        elif isinstance(content, str):",
        "            return content",
        "        return content",
        "    if 'text' in result:",
        "        return result['text']",
        "",
        "    # Nếu result là dict nhưng không có content/text, trả về toàn bộ",
        "    return result",
    ]

    func_body = "\n".join(func_body_lines)
    func_def = f"def {tool_name}({', '.join(param_signatures)}):\n{func_body}"

    # Execute để tạo function
    # Pass các functions cần thiết vào namespace để function có thể sử dụng
    namespace = {
        "__name__": __name__,
        "__builtins__": __builtins__,
        "Any": Any,  # Import Any để dùng trong function signature
        "Optional": Optional,  # Import Optional để dùng trong function signature
        "List": List,  # Import List để dùng trong function signature (List[str], List[int], etc.)
        "_call_mcp_jsonrpc_func": _call_mcp_jsonrpc,  # Alias để tránh conflict
        "_process_arguments_func": _process_arguments,  # Alias để tránh conflict
        "print": print,  # Đảm bảo print function có sẵn
    }
    exec(func_def, namespace)
    tool_function = namespace[tool_name]

    return tool_function


def _load_mcp_tools_via_http() -> List[Any]:
    """Load MCP tools từ server qua HTTP."""
    tools = []
    try:
        # List tools từ MCP server
        result = _call_mcp_jsonrpc(method="tools/list")

        if "error" in result:
            print(f"Error listing MCP tools: {result.get('error')}")
            print(f"Note: Ensure MCP server is running at {MCP_SERVER_URL}")
            print(f"Config file: {_CONFIG_FILE}")
            return []

        tools_list = result.get("tools", [])

        if not tools_list:
            print("Warning: No tools found from MCP server")
            return []

        # Tạo function tools
        for tool in tools_list:
            tool_name = tool.get("name")
            if tool_name:
                tool_func = _create_mcp_tool_function(tool_name, tool)
                tools.append(tool_func)
                # print(f"Loaded MCP tool: {tool_name}")

        print(f"Successfully loaded {len(tools)} MCP tools from {MCP_SERVER_URL}")

    except Exception as e:
        print(f"Error loading MCP tools: {e}")
        print(f"Note: Ensure MCP server is running at {MCP_SERVER_URL}")
        print(f"Config file: {_CONFIG_FILE}")

    return tools


def get_current_datetime():
    """
    Lấy ngày và giờ hiện tại (thời gian thực từ hệ thống).

    Returns:
        dict: Dictionary chứa thông tin ngày/giờ hiện tại với các format khác nhau:
            - date: YYYY-MM-DD
            - time: HH:MM:SS
            - datetime: YYYY-MM-DD HH:MM:SS
            - date_vn: DD/MM/YYYY
            - day_name: Tên thứ bằng tiếng Anh
            - day_name_vn: Tên thứ bằng tiếng Việt
            - full_vn: "DD tháng MM năm YYYY" (ví dụ: "09 tháng 11 năm 2024")
            - is_trading_hours: bool (True nếu trong giờ giao dịch: 9:00-15:00, thứ 2-6)
            - is_weekend: bool (True nếu là thứ 7 hoặc chủ nhật)

    Example:
        >>> result = get_current_datetime()
        >>> print(result["full_vn"])
        "09 tháng 11 năm 2024"
    """
    now = datetime.now()
    day_name = now.strftime("%A")
    hour = now.hour
    is_weekend = day_name in ["Saturday", "Sunday"]
    # Giờ giao dịch: 9:00-15:00, thứ 2-6
    is_trading_hours = not is_weekend and hour >= 9 and hour < 15

    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date_vn": now.strftime("%d/%m/%Y"),
        "day_name": day_name,
        "day_name_vn": {
            "Monday": "Thứ Hai",
            "Tuesday": "Thứ Ba",
            "Wednesday": "Thứ Tư",
            "Thursday": "Thứ Năm",
            "Friday": "Thứ Sáu",
            "Saturday": "Thứ Bảy",
            "Sunday": "Chủ Nhật",
        }.get(day_name, day_name),
        "full_vn": f"{now.strftime('%d')} tháng {now.strftime('%m')} năm {now.strftime('%Y')}",
        "is_trading_hours": is_trading_hours,
        "is_weekend": is_weekend,
    }


# Load MCP tools từ server
print(f"🔌 Connecting to MCP server at {MCP_SERVER_URL}")
# Initialize session trước khi load tools (có retry logic)
session_result = _initialize_mcp_session(max_retries=3)
if not session_result:
    print(
        f"⚠️  Warning: Failed to initialize MCP session. MCP tools will not be available."
    )
    print(f"   This may be due to:")
    print(f"   - MCP server is down or slow (cold start on Render.com)")
    print(f"   - Network connectivity issues")
    print(f"   - Server URL incorrect: {MCP_SERVER_URL}")
    mcp_tools = []
else:
    mcp_tools = _load_mcp_tools_via_http()
    print(f"✅ Loaded {len(mcp_tools)} MCP tools for market data")


# Tạo wrapper function cho get_quote_intraday_price với auto-fallback
def _create_smart_quote_intraday_wrapper(original_get_quote_intraday_price):
    """
    Wrapper cho get_quote_intraday_price để tự động fallback sang get_quote_history_price
    khi ngoài giờ giao dịch hoặc có lỗi.
    """

    def smart_get_quote_intraday_price(
        symbol: str,
        page_size: int = 100,
        last_time: Optional[str] = None,
        output_format: str = "json",
    ):
        """
        Get quote intraday price from stock market.
        Tự động fallback sang giá đóng cửa nếu ngoài giờ giao dịch hoặc có lỗi.

        Args:
            symbol: Stock symbol
            page_size: Number of rows to return (max: 100000)
            last_time: Last time to get intraday price from (optional)
            output_format: Output format ('json' or 'dataframe')

        Returns:
            Price data (intraday hoặc closing price nếu fallback)
        """
        # Kiểm tra khung giờ giao dịch
        now = datetime.now()
        day_name = now.strftime("%A")
        hour = now.hour
        is_weekend = day_name in ["Saturday", "Sunday"]
        is_trading_hours = not is_weekend and hour >= 9 and hour < 15

        # Thử lấy giá trong ngày trước
        try:
            result = original_get_quote_intraday_price(
                symbol=symbol,
                page_size=page_size,
                last_time=last_time,
                output_format=output_format,
            )

            # Kiểm tra nếu có lỗi
            if isinstance(result, dict) and "error" in result:
                error_msg = str(result.get("error", ""))
                print(f"[INFO] get_quote_intraday_price failed: {error_msg}")
                print(
                    f"[INFO] Falling back to get_quote_history_price for closing price"
                )
                # Fallback sang giá đóng cửa
                return _get_closing_price_fallback(symbol, output_format)

            # Nếu result là string rỗng hoặc không hợp lệ
            if not result or (isinstance(result, str) and len(result.strip()) == 0):
                print(f"[INFO] get_quote_intraday_price returned empty result")
                print(
                    f"[INFO] Falling back to get_quote_history_price for closing price"
                )
                return _get_closing_price_fallback(symbol, output_format)

            return result

        except Exception as e:
            print(f"[INFO] get_quote_intraday_price exception: {e}")
            print(f"[INFO] Falling back to get_quote_history_price for closing price")
            return _get_closing_price_fallback(symbol, output_format)

    return smart_get_quote_intraday_price


def _get_closing_price_fallback(symbol: str, output_format: str = "json"):
    """
    Fallback function để lấy giá đóng cửa khi không lấy được giá trong ngày.
    """
    try:
        # Lấy giá đóng cửa của ngày gần nhất (7 ngày gần đây)
        now = datetime.now()
        end_date = now.strftime("%Y-%m-%d")
        # Lấy 7 ngày gần đây để đảm bảo có dữ liệu (tránh ngày nghỉ)
        start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        # Gọi get_quote_history_price
        result = _call_mcp_jsonrpc(
            method="tools/call",
            params={
                "name": "get_quote_history_price",
                "arguments": {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "interval": "1D",
                    "output_format": output_format,
                },
            },
        )

        if "error" in result:
            return {
                "error": f"Failed to get closing price: {result.get('error')}",
                "tool": "get_quote_history_price",
                "fallback_from": "get_quote_intraday_price",
            }

        # Parse response - giống như trong _create_mcp_tool_function
        if "content" in result:
            content = result["content"]
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        texts.append(item["text"])
                    elif isinstance(item, str):
                        texts.append(item)
                if texts:
                    # Nếu chỉ có 1 text item, trả về trực tiếp
                    if len(texts) == 1:
                        return texts[0]
                    return "\n".join(texts)
            elif isinstance(content, str):
                return content
            return content

        if "text" in result:
            return result["text"]

        return result

    except Exception as e:
        return {
            "error": f"Failed to get closing price: {str(e)}",
            "tool": "get_quote_history_price",
            "fallback_from": "get_quote_intraday_price",
        }


# Tìm và wrap get_quote_intraday_price nếu có
tools = mcp_tools.copy()
wrapped_tools = []
for tool in tools:
    if hasattr(tool, "__name__") and tool.__name__ == "get_quote_intraday_price":
        # Wrap function này
        wrapped_tool = _create_smart_quote_intraday_wrapper(tool)
        wrapped_tools.append(wrapped_tool)
        print("✅ Wrapped get_quote_intraday_price with auto-fallback to closing price")
    else:
        wrapped_tools.append(tool)

tools = wrapped_tools

# Nếu không có MCP tools, tạo fallback tools để trả về error message thay vì crash
if not mcp_tools:
    print("⚠️  Creating fallback MCP tools to prevent agent crashes...")

    def _create_mcp_tool_fallback(tool_name: str):
        """Tạo fallback tool trả về error message khi MCP tools không available."""

        def fallback_tool(*args, **kwargs):
            return {
                "error": f"MCP server is currently unavailable. Tool '{tool_name}' cannot be used.",
                "message": (
                    f"Xin lỗi, hiện tại không thể truy cập MCP server để lấy thông tin thị trường. "
                    f"Vui lòng thử lại sau hoặc liên hệ quản trị viên. "
                    f"MCP Server URL: {MCP_SERVER_URL}"
                ),
                "tool": tool_name,
                "suggestion": "MCP server có thể đang trong trạng thái cold start hoặc gặp sự cố. Vui lòng đợi vài giây rồi thử lại.",
            }

        fallback_tool.__name__ = tool_name
        fallback_tool.__doc__ = f"Fallback tool for {tool_name} - returns error when MCP server is unavailable."
        return fallback_tool

    # Tạo các fallback tools phổ biến nhất
    common_mcp_tools = [
        "get_quote_intraday_price",
        "get_quote_history_price",
        "get_price_board",
        "get_company_overview",
        "get_company_news",
        "get_quote_price_depth",
    ]

    for tool_name in common_mcp_tools:
        fallback = _create_mcp_tool_fallback(tool_name)
        tools.append(fallback)

    print(f"✅ Created {len(common_mcp_tools)} fallback MCP tools")

# Thêm tool lấy thời gian hiện tại
tools.append(get_current_datetime)
print("✅ Added tool: get_current_datetime")

# Load backend API tools
try:
    from agents.backend_tools import (
        create_transaction,
        get_transaction_history,
        get_transaction_stats,
        get_user_profile,
        get_ranking,
        get_transaction_by_id,
        cancel_transaction,
        get_market_data,
        get_stock_data,
        get_all_stocks,
        get_vn30_history,
    )

    backend_tools = [
        create_transaction,
        get_transaction_history,
        get_transaction_stats,
        get_user_profile,
        get_ranking,
        get_transaction_by_id,
        cancel_transaction,
        get_market_data,
        get_stock_data,
        get_all_stocks,
        get_vn30_history,
    ]
    tools.extend(backend_tools)
    print(
        f"✅ Added {len(backend_tools)} backend API tools (user actions + market cache)"
    )
    print(
        f"📊 Total tools available: {len(tools)} ({len(mcp_tools)} MCP + {len(backend_tools)} Backend API + 1 custom)"
    )
except Exception as e:
    print(f"Warning: Failed to load backend tools: {e}")

if not tools:
    print(
        f"Warning: No MCP tools loaded. "
        f"Ensure MCP server is running at {MCP_SERVER_URL}"
    )

# Tạo agent với MCP tools - sử dụng OpenRouter API
# API key: set OPENROUTER_API_KEY trong .env
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
if not openrouter_api_key:
    print("⚠️  WARNING: OPENROUTER_API_KEY not found in environment variables!")
    print("   Please set OPENROUTER_API_KEY in .env file")
else:
    print(f"✅ OPENROUTER_API_KEY found: {openrouter_api_key[:10]}...")

# Set biến môi trường cho litellm (litellm tự động đọc từ env)
os.environ["OPENROUTER_API_KEY"] = openrouter_api_key or ""

# Cấu hình OpenRouter với LiteLlm
# Format model name: openrouter/provider/model hoặc provider/model
# Thử model khác nếu gpt-oss-120b:free không hoạt động
# Các model free tier phổ biến: meta-llama/llama-3.2-3b-instruct:free, google/gemini-flash-1.5:free
model_name = os.getenv("OPENROUTER_MODEL", "openrouter/openai/gpt-oss-120b:free")
print(f"🔧 Using OpenRouter model: {model_name}")

root_agent = LlmAgent(
    model=LiteLlm(
        model=model_name,
        api_key=openrouter_api_key,
        api_base="https://openrouter.ai/api/v1",
        timeout=180.0,  # Timeout 180 giây cho model free tier có thể chậm
        # Thêm headers cho OpenRouter (optional)
        extra_headers={
            "HTTP-Referer": "https://github.com/ai-core-trading",
            "X-Title": "VNStock Agent",
        },
    ),
    name="vnstock_agent",
    description=(
        "Assistant chuyên về thị trường chứng khoán Việt Nam. "
        "Có 2 loại tools: "
        "(1) MCP TOOLS (32 tools): Dùng để lấy thông tin thị trường, giá cổ phiếu, tin tức, báo cáo tài chính, thông tin công ty từ VNStock MCP server. "
        "(2) BACKEND API TOOLS (7 tools): Dùng để thực hiện hành động (mua/bán cổ phiếu) và lấy thông tin cá nhân (lịch sử giao dịch, thống kê, profile, ranking). "
        "Khi user hỏi về thông tin thị trường → LUÔN dùng MCP tools. "
        "Khi user muốn thực hiện hành động hoặc xem thông tin cá nhân → dùng Backend API tools. "
        "Có tool `get_current_datetime` để lấy ngày/giờ hiện tại chính xác."
    ),
    instruction=f"""Bạn là một assistant chuyên về thị trường chứng khoán Việt Nam.

{"⚠️  QUAN TRỌNG: MCP SERVER HIỆN KHÔNG KHẢ DỤNG" if not mcp_tools else ""}
{"- MCP tools không thể sử dụng được do MCP server không kết nối được." if not mcp_tools else ""}
{"- Khi người dùng hỏi về thông tin thị trường (giá cổ phiếu, tin tức, báo cáo tài chính), " if not mcp_tools else ""}
{"  bạn có thể gọi MCP tools, nhưng chúng sẽ trả về error message. " if not mcp_tools else ""}
{"- Khi nhận được error từ MCP tools, bạn PHẢI trả lời cho người dùng: " if not mcp_tools else ""}
{"  'Xin lỗi, hiện tại không thể truy cập dữ liệu thị trường do MCP server không khả dụng. " if not mcp_tools else ""}
{"  Vui lòng thử lại sau hoặc liên hệ quản trị viên.'" if not mcp_tools else ""}
{"- Chỉ có thể sử dụng backend API tools (giao dịch, lịch sử, thống kê) và get_current_datetime." if not mcp_tools else ""}

QUAN TRỌNG VỀ PHÂN LOẠI TOOLS:

1. MCP TOOLS (ƯU TIÊN CHO THÔNG TIN THỊ TRƯỜNG):
   - LUÔN sử dụng MCP tools để lấy thông tin thị trường, giá cổ phiếu, thông tin công ty
   - MCP tools có 32 tools bao gồm:
     * Thông tin công ty: get_company_overview, get_company_news, get_company_events, get_company_shareholders, get_company_officers, get_company_subsidiaries, get_company_reports, get_company_dividends, get_company_insider_deals, get_company_ratio_summary, get_company_trading_stats
     * Dữ liệu giá: get_quote_history_price, get_quote_intraday_price, get_quote_price_depth, get_price_board
     * Báo cáo tài chính: get_income_statements, get_balance_sheets, get_cash_flows, get_finance_ratios, get_raw_report
     * Thông tin quỹ: list_all_funds, search_fund, get_fund_nav_report, get_fund_top_holding, get_fund_industry_holding, get_fund_asset_holding
     * Danh sách mã: get_all_symbol_groups, get_all_industries, get_all_symbols_by_group, get_all_symbols_by_industry, get_all_symbols
     * Khác: get_gold_price, get_exchange_rate

2. BACKEND API TOOLS (CHỈ DÙNG NẾU THIẾU THÔNG TIN, THỰC HIỆN USER ACTIONS, THÔNG TIN USER VÀ MARKET CACHE):
   - Sử dụng backend API tools khi:
     * THIẾU THÔNG TIN VỀ HỆ THỐNG
     * User muốn THỰC HIỆN HÀNH ĐỘNG: mua/bán cổ phiếu (create_transaction), hủy giao dịch (cancel_transaction)
     * User muốn xem THÔNG TIN CÁ NHÂN: lịch sử giao dịch (get_transaction_history), thống kê giao dịch (get_transaction_stats), thông tin tài khoản (get_user_profile), bảng xếp hạng (get_ranking)
     * User muốn xem MARKET CACHE (dữ liệu đã cache): get_market_data, get_stock_data, get_all_stocks, get_vn30_history
   - LƯU Ý: userId sẽ được tự động lấy từ metadata, không cần user cung cấp trong message
   - KHÔNG BAO GIỜ dùng backend API để lấy thông tin thị trường real-time (giá, tin tức, báo cáo tài chính) - phải dùng MCP tools

QUY TẮC SỬ DỤNG TOOLS:
- Khi user hỏi về giá cổ phiếu, tin tức, báo cáo tài chính → DÙNG MCP TOOLS
- Khi user muốn mua/bán cổ phiếu → DÙNG MCP TOOLS để lấy giá hiện tại, SAU ĐÓ dùng create_transaction để thực hiện
- Khi user hỏi về thông tin cá nhân, giao dịch của họ → DÙNG BACKEND API TOOLS
- Khi user hỏi về bảng xếp hạng → DÙNG BACKEND API TOOLS (get_ranking)

QUAN TRỌNG VỀ THỜI GIAN VÀ DỮ LIỆU:
- Khi người dùng hỏi về ngày/giờ hiện tại, LUÔN sử dụng tool `get_current_datetime` để lấy thời gian THỰC TẾ
- KHÔNG BAO GIỜ tự đoán hoặc dùng kiến thức cũ về ngày tháng
- Luôn sử dụng tools để lấy dữ liệu THỰC TẾ từ MCP server
- KHÔNG BAO GIỜ tự tạo hoặc đoán dữ liệu
- Nếu tool trả về dữ liệu, hãy sử dụng dữ liệu đó chính xác
- Nếu tool trả về lỗi, hãy thông báo lỗi rõ ràng cho người dùng
- Luôn kiểm tra kết quả từ tools trước khi trả lời

QUAN TRỌNG VỀ FORMAT RESPONSE:
- BẮT BUỘC: LUÔN trả lời bằng một đoạn text đầy đủ, rõ ràng bằng tiếng Việt
- KHÔNG BAO GIỜ chỉ trả về dữ liệu thô hoặc để trống response text
- Mỗi câu trả lời phải là một đoạn văn hoàn chỉnh, giải thích rõ ràng cho người dùng
- Ví dụ: Khi người dùng hỏi "Cho mình xem tổng quan thị trường hôm nay", bạn phải trả lời: "Dựa trên dữ liệu thị trường hôm nay, [mô tả chi tiết về tình hình thị trường]..."
- Ví dụ: Khi người dùng hỏi "Mình muốn mua cổ phiếu MWG", bạn phải trả lời: "Tôi sẽ hướng dẫn bạn mua cổ phiếu MWG. [giải thích các bước và thông tin cần thiết]..."

Khi người dùng hỏi về THÔNG TIN THỊ TRƯỜNG (giá cổ phiếu, tin tức, báo cáo tài chính, thông tin công ty):
1. Xác định loại thông tin cần thiết
2. LUÔN sử dụng MCP TOOLS để lấy dữ liệu THỰC TẾ (KHÔNG dùng backend API)
3. Ví dụ: "Giá VCB hôm nay" → dùng get_quote_intraday_price hoặc get_price_board
   - Tool get_quote_intraday_price TỰ ĐỘNG fallback sang giá đóng cửa nếu ngoài giờ giao dịch (9:00-15:00, thứ 2-6) hoặc có lỗi
   - Nếu là chủ nhật hoặc ngoài giờ giao dịch, tool sẽ tự động lấy giá đóng cửa của ngày gần nhất
4. Ví dụ: "Tin tức về MWG" → dùng get_company_news
5. Ví dụ: "Báo cáo tài chính VNM" → dùng get_income_statements, get_balance_sheets
6. Kiểm tra kết quả từ tool
7. Phân tích và trình bày kết quả một cách rõ ràng, chính xác, dễ hiểu BẰNG MỘT ĐOẠN VĂN HOÀN CHỈNH
8. Nếu không có dữ liệu hoặc có lỗi, hãy giải thích lý do và đề xuất cách khác BẰNG TEXT

QUAN TRỌNG VỀ XỬ LÝ CÂU HỎI KHÔNG RÕ RÀNG - HIỂN THỊ MẶC ĐỊNH:
- Khi người dùng hỏi về "tin tức thị trường", "diễn biến thị trường", "tình hình thị trường", "thị trường hôm nay" mà KHÔNG chỉ định mã cụ thể:
  → MẶC ĐỊNH: Sử dụng `get_all_symbols_by_group` với group="VN30" để lấy danh sách mã VN30
  → Nếu thành công: Sử dụng `get_price_board` với danh sách mã VN30 vừa lấy được
  → Nếu thất bại: Sử dụng `get_price_board` với danh sách mã phổ biến mặc định: ["VCB", "VIC", "VHM", "HPG", "MSN", "MWG", "FPT", "VNM", "TCB", "BID", "CTG", "MBB", "VPB", "TPB", "ACB", "STB", "HDB", "SSI", "VCI", "GAS", "PLX", "POW", "GVR", "VSH", "VGC", "DXG", "VRE", "VHC", "VND", "VJC"]
  → HIỂN THỊ kết quả bảng giá (diễn biến thị trường) ngay lập tức
  → SAU ĐÓ hỏi: "Bạn có muốn xem tin tức về mã cụ thể nào không? Hoặc muốn xem giá của mã khác?"

- Khi người dùng hỏi về "tin tức về công ty", "tin tức công ty", "news công ty" mà KHÔNG chỉ định mã cụ thể:
  → MẶC ĐỊNH: Giả định người dùng muốn xem tin tức kinh doanh/tài chính
  → HỎI LẠI: "Bạn muốn xem tin tức về công ty nào? Vui lòng cung cấp mã cổ phiếu (ví dụ: VCB, VNM, FPT, ...)"
  → SAU KHI CÓ MÃ: Sử dụng `get_company_news` với symbol được cung cấp, page_size=10 (mặc định), page=0 (mặc định)

- Khi người dùng hỏi về "tin tức về [MÃ]" (ví dụ: "tin tức về VCB"):
  → Sử dụng `get_company_news` với symbol cụ thể, page_size=10, page=0
  → HIỂN THỊ kết quả ngay lập tức

- Khi người dùng hỏi về "giá cổ phiếu", "bảng giá" mà KHÔNG chỉ định mã cụ thể:
  → MẶC ĐỊNH: Sử dụng `get_price_board` với danh sách mã VN30 (như trên)
  → HIỂN THỊ kết quả ngay lập tức
  → SAU ĐÓ hỏi: "Bạn có muốn xem giá của mã cụ thể nào khác không?"

- Khi người dùng hỏi về "báo cáo tài chính", "báo cáo" mà KHÔNG chỉ định mã cụ thể:
  → HỎI LẠI: "Bạn muốn xem báo cáo tài chính của công ty nào? Vui lòng cung cấp mã cổ phiếu (ví dụ: VCB, VNM, FPT, ...)"
  → SAU KHI CÓ MÃ: Sử dụng `get_income_statements`, `get_balance_sheets`, `get_cash_flows` với symbol được cung cấp

NGUYÊN TẮC CHUNG:
- LUÔN hiển thị output mặc định TRƯỚC (nếu có thể suy luận được)
- SAU ĐÓ mới hỏi lại thông tin cần thiết nếu thiếu hoặc muốn chi tiết hơn
- Nếu không thể suy luận được (ví dụ: thiếu mã cổ phiếu cho get_company_news), hỏi lại ngay nhưng vẫn cung cấp context về những gì sẽ hiển thị

Khi người dùng muốn MUA cổ phiếu:
1. Xác định mã cổ phiếu (symbol), khối lượng (quantity), giá (price) từ câu hỏi
2. userId sẽ được tự động lấy từ metadata (không cần user cung cấp trong message)
3. BƯỚC 1: LUÔN lấy giá hiện tại bằng MCP TOOL (get_quote_intraday_price hoặc get_price_board) - KHÔNG dùng backend API
4. BƯỚC 2: Nếu người dùng đã cung cấp đủ thông tin (symbol, quantity, price), sử dụng BACKEND API TOOL `create_transaction` để thực hiện giao dịch (userId sẽ tự động được lấy)
5. Nếu thiếu thông tin, hướng dẫn người dùng cung cấp đầy đủ thông tin cần thiết
6. Trả lời bằng text rõ ràng về kết quả giao dịch hoặc hướng dẫn tiếp theo

Khi người dùng muốn BÁN cổ phiếu:
1. Xác định mã cổ phiếu (symbol), khối lượng (quantity), giá (price) từ câu hỏi
2. userId sẽ được tự động lấy từ metadata (không cần user cung cấp trong message)
3. BƯỚC 1: LUÔN lấy giá hiện tại bằng MCP TOOL (get_quote_intraday_price hoặc get_price_board) - KHÔNG dùng backend API
4. BƯỚC 2: Nếu người dùng đã cung cấp đủ thông tin, sử dụng BACKEND API TOOL `create_transaction` với type="sell" để thực hiện giao dịch (userId sẽ tự động được lấy)
5. Nếu thiếu thông tin, hướng dẫn người dùng cung cấp đầy đủ thông tin cần thiết
6. Trả lời bằng text rõ ràng về kết quả giao dịch hoặc hướng dẫn tiếp theo

Khi người dùng hỏi về LỊCH SỬ GIAO DỊCH:
1. userId sẽ được tự động lấy từ metadata (không cần user cung cấp trong message)
2. Sử dụng tool `get_transaction_history` để lấy lịch sử giao dịch (không cần truyền userId, tool sẽ tự động lấy)
3. Trả lời bằng text tóm tắt lịch sử giao dịch dựa trên kết quả từ tool

Khi người dùng hỏi về THỐNG KÊ GIAO DỊCH:
1. userId sẽ được tự động lấy từ metadata (không cần user cung cấp trong message)
2. Sử dụng tool `get_transaction_stats` để lấy thống kê (không cần truyền userId, tool sẽ tự động lấy)
3. Trả lời bằng text trình bày thống kê (lợi nhuận, số lượng giao dịch, tỷ lệ thắng, etc.)

Khi người dùng hỏi về TÀI KHOẢN hoặc PROFILE:
1. userId sẽ được tự động lấy từ metadata (không cần user cung cấp trong message)
2. Sử dụng tool `get_user_profile` để lấy thông tin tài khoản (không cần truyền userId, tool sẽ tự động lấy)
3. Trả lời bằng text trình bày thông tin tài khoản (số dư, thông tin cá nhân, etc.)

Khi người dùng hỏi về BẢNG XẾP HẠNG:
1. Sử dụng tool `get_ranking` để lấy bảng xếp hạng
2. Trả lời bằng text trình bày bảng xếp hạng top người dùng

Khi người dùng hỏi về ngày/giờ hiện tại:
1. LUÔN gọi tool `get_current_datetime` để lấy thời gian thực
2. Sử dụng kết quả từ tool để trả lời chính xác BẰNG MỘT CÂU VĂN HOÀN CHỈNH
3. KHÔNG BAO GIỜ tự đoán hoặc dùng kiến thức cũ về ngày tháng

Luôn trả lời bằng tiếng Việt và cung cấp thông tin chính xác, đầy đủ dựa trên dữ liệu THỰC TẾ từ MCP server. MỖI RESPONSE PHẢI LÀ MỘT ĐOẠN TEXT HOÀN CHỈNH, KHÔNG ĐƯỢC ĐỂ TRỐNG.""",
    tools=tools,
)
