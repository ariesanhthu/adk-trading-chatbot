"""
Cấu hình cho VNStock Agent.

Quản lý việc load cấu hình từ file YAML và environment variables.
"""

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

# Load biến môi trường từ .env nếu có
load_dotenv()


class AgentConfig:
    """Quản lý cấu hình cho Agent."""

    # Đường dẫn đến thư mục configs
    CONFIG_DIR = Path(__file__).parent.parent / "configs"
    MCP_CONFIG_FILE = CONFIG_DIR / "mcp_config.yaml"

    def __init__(self):
        """Khởi tạo và load cấu hình."""
        self._mcp_config = self._load_mcp_config()
        self.mcp_server_url = self._get_mcp_server_url()
        self.mcp_timeout = self._get_mcp_timeout()

    def _load_mcp_config(self) -> Dict[str, Any]:
        """
        Load cấu hình MCP từ file YAML.

        Returns:
            Dict chứa cấu hình MCP server, hoặc dict rỗng nếu có lỗi
        """
        try:
            if self.MCP_CONFIG_FILE.exists():
                with open(self.MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    return config.get("mcp_server", {})
        except Exception as e:
            print(f"Warning: Failed to load config from {self.MCP_CONFIG_FILE}: {e}")
        return {}

    def _get_mcp_server_url(self) -> str:
        """
        Lấy MCP server URL.

        Ưu tiên: environment variable > config file > default

        Returns:
            URL của MCP server
        """
        return os.getenv(
            "MCP_SERVER_URL",
            self._mcp_config.get(
                "url", "https://mcp-server-vietnam-stock-trading.onrender.com"
            ),
        )

    def _get_mcp_timeout(self) -> float:
        """
        Lấy timeout cho MCP requests.

        Ưu tiên: environment variable > config file > default (60.0s)

        Returns:
            Timeout value (seconds)
        """
        return float(
            os.getenv("MCP_TIMEOUT", str(self._mcp_config.get("timeout", 60.0)))
        )

    @staticmethod
    def get_env_var(key: str, default: Any = None) -> Any:
        """
        Lấy giá trị environment variable.

        Args:
            key: Tên biến môi trường
            default: Giá trị mặc định nếu không tìm thấy

        Returns:
            Giá trị biến môi trường hoặc default
        """
        return os.getenv(key, default)
