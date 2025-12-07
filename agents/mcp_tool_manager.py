"""
MCP Tool Manager - Quản lý MCP tools.

Load, tạo và wrap MCP tools từ server.
"""

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from agents.mcp_client import MCPClient


class MCPToolManager:
    """Quản lý MCP tools: load, tạo function, wrap với fallback."""

    def __init__(self, mcp_client: MCPClient):
        """
        Khởi tạo MCP Tool Manager.

        Args:
            mcp_client: MCPClient instance để gọi MCP server
        """
        self.mcp_client = mcp_client

    @staticmethod
    def _process_arguments(
        tool_name: str, properties: Dict, tool_param_mapping: Dict, **kwargs
    ) -> Dict[str, Any]:
        """
        Process và validate arguments từ kwargs.

        Args:
            tool_name: Tên tool
            properties: Schema properties của tool
            tool_param_mapping: Mapping các parameter names
            **kwargs: Arguments từ LLM

        Returns:
            Processed kwargs
        """
        processed_kwargs = {}

        # Áp dụng parameter mapping nếu có
        normalized_kwargs = {}
        for key, value in kwargs.items():
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
                    processed_kwargs[param_name] = [param_value]
                elif isinstance(param_value, list):
                    processed_kwargs[param_name] = param_value
                else:
                    processed_kwargs[param_name] = [str(param_value)]
            # Xử lý array/list types
            elif param_type == "array" or (
                isinstance(param_type, list) and "array" in param_type
            ):
                if isinstance(param_value, str):
                    processed_kwargs[param_name] = [param_value]
                elif isinstance(param_value, list):
                    processed_kwargs[param_name] = param_value
                else:
                    processed_kwargs[param_name] = [param_value]
            # Xử lý string types
            elif param_type == "string":
                if param_value is None:
                    processed_kwargs[param_name] = None
                elif isinstance(param_value, list):
                    if len(param_value) > 0:
                        processed_kwargs[param_name] = str(param_value[0])
                    else:
                        processed_kwargs[param_name] = ""
                else:
                    processed_kwargs[param_name] = str(param_value)
            else:
                # Giữ nguyên giá trị cho các type khác
                processed_kwargs[param_name] = param_value

        return processed_kwargs

    @staticmethod
    def _get_tool_param_mapping(properties: Dict, tool_name: str) -> Dict[str, str]:
        """
        Tạo parameter mapping cho tool.

        Args:
            properties: Schema properties
            tool_name: Tên tool

        Returns:
            Parameter mapping dict
        """
        tool_param_mapping = {}

        # Kiểm tra xem tool có parameter "symbol" hay "symbols"
        has_symbols = "symbols" in properties
        has_symbol = "symbol" in properties

        if has_symbols:
            # Tool cần "symbols" (list)
            tool_param_mapping = {
                "symbol": "symbols",
                "symbol_list": "symbols",
                "stocks": "symbols",
                "stock": "symbols",
            }
        elif has_symbol:
            # Tool cần "symbol" (string)
            tool_param_mapping = {
                "symbols": "symbol",
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

        return tool_param_mapping

    def _create_mcp_tool_function(
        self, tool_name: str, tool_schema: Dict[str, Any]
    ) -> Callable:
        """
        Tạo function tool từ MCP tool schema.

        Args:
            tool_name: Tên tool
            tool_schema: Schema của tool từ MCP server

        Returns:
            Function tool có thể gọi được
        """
        from typing import Any, List, Optional

        description = tool_schema.get("description", f"MCP tool: {tool_name}")
        input_schema = tool_schema.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        # Tạo parameter mapping
        tool_param_mapping = self._get_tool_param_mapping(properties, tool_name)

        # Tạo docstring chi tiết từ schema
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
        param_signatures = []
        for param_name, param_schema in properties.items():
            param_type = param_schema.get("type", "Any")
            default = param_schema.get("default")
            is_required = param_name in required

            # Tạo type annotation string
            if param_type == "array":
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
                param_signatures.append(f"{param_name}: {type_annotation}")
            else:
                if default is not None:
                    if isinstance(default, str):
                        default_str = f'"{default}"'
                    else:
                        default_str = str(default)
                    param_signatures.append(
                        f"{param_name}: {type_annotation} = {default_str}"
                    )
                else:
                    param_signatures.append(
                        f"{param_name}: Optional[{type_annotation}] = None"
                    )

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
            "    # Kiểm tra lỗi",
            "    if isinstance(result, dict):",
            "        if 'error' in result:",
            "            error_msg = result.get('error', 'Unknown error')",
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
        # Pass các functions cần thiết vào namespace
        namespace = {
            "__name__": __name__,
            "__builtins__": __builtins__,
            "Any": Any,
            "Optional": Optional,
            "List": List,
            "_call_mcp_jsonrpc_func": self.mcp_client.call_jsonrpc,
            "_process_arguments_func": MCPToolManager._process_arguments,  # Static method
            "print": print,
        }
        exec(func_def, namespace)
        tool_function = namespace[tool_name]

        return tool_function

    def load_tools(self) -> List[Callable]:
        """
        Load MCP tools từ server.

        Returns:
            List các function tools
        """
        tools = []
        try:
            # List tools từ MCP server
            result = self.mcp_client.call_jsonrpc(method="tools/list")

            if "error" in result:
                print(f"Error listing MCP tools: {result.get('error')}")
                print(
                    f"Note: Ensure MCP server is running at {self.mcp_client.server_url}"
                )
                return []

            tools_list = result.get("tools", [])

            if not tools_list:
                print("Warning: No tools found from MCP server")
                return []

            # Tạo function tools
            for tool in tools_list:
                tool_name = tool.get("name")
                if tool_name:
                    tool_func = self._create_mcp_tool_function(tool_name, tool)
                    tools.append(tool_func)

            print(
                f"Successfully loaded {len(tools)} MCP tools from {self.mcp_client.server_url}"
            )

        except Exception as e:
            print(f"Error loading MCP tools: {e}")
            print(f"Note: Ensure MCP server is running at {self.mcp_client.server_url}")

        return tools

    def _get_closing_price_fallback(
        self, symbol: str, output_format: str = "json"
    ) -> Any:
        """
        Fallback function để lấy giá đóng cửa khi không lấy được giá trong ngày.

        Args:
            symbol: Mã cổ phiếu
            output_format: Format output

        Returns:
            Giá đóng cửa hoặc error dict
        """
        try:
            # Lấy giá đóng cửa của ngày gần nhất (7 ngày gần đây)
            now = datetime.now()
            end_date = now.strftime("%Y-%m-%d")
            start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")

            # Gọi get_quote_history_price
            result = self.mcp_client.call_jsonrpc(
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

            # Parse response
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

    def wrap_intraday_price_tool(self, original_tool: Callable) -> Callable:
        """
        Wrap get_quote_intraday_price với auto-fallback sang giá đóng cửa.

        Args:
            original_tool: Tool function gốc

        Returns:
            Wrapped tool function
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
            """
            # Kiểm tra khung giờ giao dịch
            now = datetime.now()
            day_name = now.strftime("%A")
            hour = now.hour
            is_weekend = day_name in ["Saturday", "Sunday"]
            is_trading_hours = not is_weekend and hour >= 9 and hour < 15

            # Thử lấy giá trong ngày trước
            try:
                result = original_tool(
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
                    return self._get_closing_price_fallback(symbol, output_format)

                # Nếu result là string rỗng hoặc không hợp lệ
                if not result or (isinstance(result, str) and len(result.strip()) == 0):
                    print(f"[INFO] get_quote_intraday_price returned empty result")
                    print(
                        f"[INFO] Falling back to get_quote_history_price for closing price"
                    )
                    return self._get_closing_price_fallback(symbol, output_format)

                return result

            except Exception as e:
                print(f"[INFO] get_quote_intraday_price exception: {e}")
                print(
                    f"[INFO] Falling back to get_quote_history_price for closing price"
                )
                return self._get_closing_price_fallback(symbol, output_format)

        return smart_get_quote_intraday_price

    def wrap_tools_with_fallback(self, tools: List[Callable]) -> List[Callable]:
        """
        Wrap các tools với fallback logic nếu cần.

        Args:
            tools: List các tools gốc

        Returns:
            List các tools đã được wrap
        """
        wrapped_tools = []
        for tool in tools:
            if (
                hasattr(tool, "__name__")
                and tool.__name__ == "get_quote_intraday_price"
            ):
                wrapped_tool = self.wrap_intraday_price_tool(tool)
                wrapped_tools.append(wrapped_tool)
                print(
                    "✅ Wrapped get_quote_intraday_price with auto-fallback to closing price"
                )
            else:
                wrapped_tools.append(tool)

        return wrapped_tools

    @staticmethod
    def create_fallback_tools(server_url: str) -> List[Callable]:
        """
        Tạo fallback tools khi MCP server không available.

        Args:
            server_url: URL của MCP server

        Returns:
            List các fallback tools
        """

        def _create_fallback_tool(tool_name: str):
            """Tạo fallback tool trả về error message."""

            def fallback_tool(*args, **kwargs):
                return {
                    "error": f"MCP server is currently unavailable. Tool '{tool_name}' cannot be used.",
                    "message": (
                        f"Xin lỗi, hiện tại không thể truy cập MCP server để lấy thông tin thị trường. "
                        f"Vui lòng thử lại sau hoặc liên hệ quản trị viên. "
                        f"MCP Server URL: {server_url}"
                    ),
                    "tool": tool_name,
                    "suggestion": (
                        "MCP server có thể đang trong trạng thái cold start hoặc gặp sự cố. "
                        "Vui lòng đợi vài giây rồi thử lại."
                    ),
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

        fallback_tools = []
        for tool_name in common_mcp_tools:
            fallback = _create_fallback_tool(tool_name)
            fallback_tools.append(fallback)

        return fallback_tools
