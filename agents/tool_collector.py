"""
Tool Collector - Thu thập và quản lý tất cả tools cho Agent.

Bao gồm: MCP tools, Backend API tools, và custom tools.
"""

from datetime import datetime
from typing import Any, Callable, List

from agents.mcp_client import MCPClient
from agents.mcp_tool_manager import MCPToolManager


def get_current_datetime() -> dict:
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
        "full_vn": (
            f"{now.strftime('%d')} tháng {now.strftime('%m')} năm {now.strftime('%Y')}"
        ),
        "is_trading_hours": is_trading_hours,
        "is_weekend": is_weekend,
    }


class ToolCollector:
    """Thu thập và quản lý tất cả tools cho Agent."""

    def __init__(self, mcp_client: MCPClient):
        """
        Khởi tạo ToolCollector.

        Args:
            mcp_client: MCPClient instance
        """
        self.mcp_client = mcp_client
        self.mcp_tool_manager = MCPToolManager(mcp_client)
        self.mcp_tools: List[Callable] = []
        self.backend_tools: List[Callable] = []
        self.custom_tools: List[Callable] = []

    def load_mcp_tools(self) -> List[Callable]:
        """
        Load MCP tools từ server.

        Returns:
            List các MCP tools
        """
        print(f"🔌 Connecting to MCP server at {self.mcp_client.server_url}")

        # Initialize session trước khi load tools
        session_result = self.mcp_client.initialize_session(max_retries=3)
        if not session_result:
            print(
                f"⚠️  Warning: Failed to initialize MCP session. "
                f"MCP tools will not be available."
            )
            print(f"   This may be due to:")
            print(f"   - MCP server is down or slow (cold start on Render.com)")
            print(f"   - Network connectivity issues")
            print(f"   - Server URL incorrect: {self.mcp_client.server_url}")
            self.mcp_tools = []
            return []

        # Load tools từ server
        self.mcp_tools = self.mcp_tool_manager.load_tools()
        print(f"✅ Loaded {len(self.mcp_tools)} MCP tools for market data")

        # Wrap tools với fallback logic
        self.mcp_tools = self.mcp_tool_manager.wrap_tools_with_fallback(self.mcp_tools)

        return self.mcp_tools

    def create_fallback_mcp_tools(self) -> List[Callable]:
        """
        Tạo fallback MCP tools khi server không available.

        Returns:
            List các fallback tools
        """
        print("⚠️  Creating fallback MCP tools to prevent agent crashes...")
        fallback_tools = MCPToolManager.create_fallback_tools(
            self.mcp_client.server_url
        )
        print(f"✅ Created {len(fallback_tools)} fallback MCP tools")
        return fallback_tools

    def load_backend_tools(self) -> List[Callable]:
        """
        Load Backend API tools.

        Returns:
            List các backend tools
        """
        try:
            from agents.backend_tools import (
                cancel_transaction,
                create_transaction,
                get_all_stocks,
                get_market_data,
                get_ranking,
                get_stock_data,
                get_transaction_by_id,
                get_transaction_history,
                get_transaction_stats,
                get_user_profile,
                get_vn30_history,
                suggest_stocks,
            )

            self.backend_tools = [
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
                suggest_stocks,
            ]

            print(
                f"✅ Added {len(self.backend_tools)} backend API tools "
                "(user actions + market cache + stock suggestions)"
            )
            return self.backend_tools

        except Exception as e:
            print(f"Warning: Failed to load backend tools: {e}")
            return []

    def load_custom_tools(self) -> List[Callable]:
        """
        Load custom tools (như get_current_datetime).

        Returns:
            List các custom tools
        """
        self.custom_tools = [get_current_datetime]
        print("✅ Added tool: get_current_datetime")
        return self.custom_tools

    def collect_all_tools(self) -> List[Callable]:
        """
        Thu thập tất cả tools: MCP, Backend, Custom.

        Returns:
            List tất cả tools
        """
        all_tools = []

        # Load MCP tools
        mcp_tools = self.load_mcp_tools()
        all_tools.extend(mcp_tools)

        # Nếu không có MCP tools, tạo fallback
        if not mcp_tools:
            fallback_tools = self.create_fallback_mcp_tools()
            all_tools.extend(fallback_tools)

        # Load Backend tools
        backend_tools = self.load_backend_tools()
        all_tools.extend(backend_tools)

        # Load Custom tools
        custom_tools = self.load_custom_tools()
        all_tools.extend(custom_tools)

        # Log tổng kết
        print(
            f"📊 Total tools available: {len(all_tools)} "
            f"({len(mcp_tools)} MCP + {len(backend_tools)} Backend API + "
            f"{len(custom_tools)} custom)"
        )

        if not all_tools:
            print(
                f"Warning: No tools loaded. "
                f"Ensure MCP server is running at {self.mcp_client.server_url}"
            )

        return all_tools

    def get_mcp_tools_count(self) -> int:
        """
        Lấy số lượng MCP tools.

        Returns:
            Số lượng MCP tools
        """
        return len(self.mcp_tools)
