"""
Backend API Tools cho Agent - Gọi các API backend để thực hiện giao dịch và lấy thông tin.

Agent có thể sử dụng các tools này để:
- Tạo giao dịch mua/bán cổ phiếu (POST)
- Lấy lịch sử giao dịch (GET)
- Lấy thống kê giao dịch (GET)
- Lấy thông tin user profile (GET)
- Lấy bảng xếp hạng (GET)
- Lấy market data từ cache (GET)
"""

import json
import os
import re
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()

# Backend API base URL từ .env
BE_API_BASE = os.getenv("BE_API", "").strip()
if not BE_API_BASE:
    print("⚠️  Warning: BE_API not found in .env. Backend tools will not work.")
    print(
        "   Please set BE_API in .env file (e.g., BE_API=https://ec2-3-25-106-203.ap-southeast-2.compute.amazonaws.com:4000/v1/api)"
    )
else:
    print(f"✅ Backend API configured: {BE_API_BASE}")

# Authentication token (optional - chỉ cần cho các endpoint có auth)
BE_API_TOKEN = os.getenv("BE_API_TOKEN", "").strip()

# Timeout cho HTTP requests
HTTP_TIMEOUT = 30.0

# Global context để lưu user_id từ conversation (tạm thời)
# Sẽ được set khi agent được gọi với user_id
_current_user_id: Optional[str] = None


def _set_current_user_id(user_id: Optional[str]):
    """Set current user_id cho backend tools (internal use)."""
    global _current_user_id
    _current_user_id = user_id


def _extract_user_id_from_message(user_message: Optional[str] = None) -> Optional[str]:
    """
    Extract user_id từ user message hoặc global context.

    User message có thể chứa: [USER_ID: user_id] ở đầu message
    Hoặc: "User ID của mình là user_id"
    """
    global _current_user_id

    # Ưu tiên lấy từ global context
    if _current_user_id:
        return _current_user_id

    # Nếu không có, thử extract từ message
    if user_message:
        # Pattern 1: [USER_ID: user_id]
        match = re.search(r"\[USER_ID:\s*([^\]]+)\]", user_message)
        if match:
            return match.group(1).strip()

        # Pattern 2: "User ID của mình là user_id"
        match = re.search(
            r"User ID (?:của mình|của tôi|mình|tôi) (?:là|is)\s+([a-zA-Z0-9_-]+)",
            user_message,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

        # Pattern 3: "userId: user_id" hoặc "user_id: user_id"
        match = re.search(
            r"(?:userId|user_id|userID)\s*[:=]\s*([a-zA-Z0-9_-]+)",
            user_message,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

    return None


def _call_backend_api(
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    require_auth: bool = False,
) -> Dict[str, Any]:
    """
    Gọi backend API. Tự động thử HTTP nếu HTTPS fail với SSL error.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint (relative to BE_API_BASE)
        data: Request body (for POST/PUT)
        params: Query parameters (for GET)
        headers: Additional headers
        require_auth: Nếu True, sẽ thêm Authorization header nếu có token

    Returns:
        Dict chứa response hoặc error
    """
    if not BE_API_BASE:
        return {
            "error": "BE_API not configured. Please set BE_API in .env file.",
            "endpoint": endpoint,
        }

    url = f"{BE_API_BASE.rstrip('/')}/{endpoint.lstrip('/')}"

    default_headers = {"Content-Type": "application/json"}

    # Thêm Authorization header nếu cần
    if require_auth and BE_API_TOKEN:
        default_headers["Authorization"] = f"Bearer {BE_API_TOKEN}"
    elif require_auth and not BE_API_TOKEN:
        return {
            "error": "Authentication required",
            "message": "This endpoint requires authentication but BE_API_TOKEN is not set in .env file.",
            "endpoint": endpoint,
            "suggestion": "Set BE_API_TOKEN in .env file with your JWT token",
        }

    if headers:
        default_headers.update(headers)

    try:
        # Tự động thử HTTP nếu HTTPS fail (cho port không SSL)
        # Disable SSL verification nếu cần (cho development)
        verify_ssl = os.getenv("BE_API_VERIFY_SSL", "true").lower() == "true"

        with httpx.Client(timeout=HTTP_TIMEOUT, verify=verify_ssl) as client:
            if method.upper() == "GET":
                resp = client.get(url, params=params, headers=default_headers)
            elif method.upper() == "POST":
                resp = client.post(url, json=data, headers=default_headers)
            elif method.upper() == "PUT":
                resp = client.put(url, json=data, headers=default_headers)
            elif method.upper() == "DELETE":
                resp = client.delete(url, headers=default_headers)
            else:
                return {
                    "error": f"Unsupported HTTP method: {method}",
                    "endpoint": endpoint,
                }

            resp.raise_for_status()
            return resp.json()

    except httpx.HTTPStatusError as e:
        try:
            error_body = e.response.json()
        except:
            error_body = {"message": e.response.text}

        return {
            "error": f"HTTP {e.response.status_code}",
            "message": error_body.get("message", str(e)),
            "status_code": e.response.status_code,
            "endpoint": endpoint,
        }

    except httpx.RequestError as e:
        error_msg = str(e)
        # Nếu lỗi SSL và URL là HTTPS, thử HTTP
        if "SSL" in error_msg or "wrong version number" in error_msg:
            if url.startswith("https://"):
                http_url = url.replace("https://", "http://", 1)
                print(f"⚠️  SSL error detected. Retrying with HTTP: {http_url}")
                try:
                    with httpx.Client(timeout=HTTP_TIMEOUT, verify=False) as client:
                        if method.upper() == "GET":
                            resp = client.get(
                                http_url, params=params, headers=default_headers
                            )
                        elif method.upper() == "POST":
                            resp = client.post(
                                http_url, json=data, headers=default_headers
                            )
                        elif method.upper() == "PUT":
                            resp = client.put(
                                http_url, json=data, headers=default_headers
                            )
                        elif method.upper() == "DELETE":
                            resp = client.delete(http_url, headers=default_headers)
                        else:
                            return {
                                "error": f"Unsupported HTTP method: {method}",
                                "endpoint": endpoint,
                            }
                        resp.raise_for_status()
                        return resp.json()
                except Exception as retry_e:
                    return {
                        "error": "Request failed (tried both HTTPS and HTTP)",
                        "message": f"HTTPS error: {error_msg}, HTTP retry error: {str(retry_e)}",
                        "endpoint": endpoint,
                        "suggestion": "Check if BE_API URL uses correct protocol (http:// or https://)",
                    }

        return {
            "error": "Request failed",
            "message": error_msg,
            "endpoint": endpoint,
        }

    except Exception as e:
        return {
            "error": "Unexpected error",
            "message": str(e),
            "endpoint": endpoint,
        }


def create_transaction(
    symbol: str,
    type: str,  # "buy" hoặc "sell"
    quantity: int,
    price: float,
    userId: Optional[str] = None,  # Optional - sẽ tự động lấy từ context nếu không có
    orderType: str = "limit",  # "limit" hoặc "market"
) -> Dict[str, Any]:
    """
    Tạo giao dịch mua/bán cổ phiếu.

    Args:
        symbol: Mã cổ phiếu (ví dụ: "MWG", "VCB")
        type: Loại giao dịch ("buy" hoặc "sell")
        quantity: Số lượng cổ phiếu
        price: Giá đặt lệnh (VNĐ)
        userId: ID người dùng (optional - sẽ tự động lấy từ context nếu không có)
        orderType: Loại lệnh ("limit" hoặc "market", default: "limit")

    Returns:
        Dict chứa thông tin giao dịch đã tạo hoặc error

    Example:
        >>> result = create_transaction(
        ...     symbol="MWG",
        ...     type="buy",
        ...     quantity=100,
        ...     price=125000,
        ...     orderType="limit"
        ... )
        >>> print(result.get("metadata", {}).get("transactionId"))
    """
    # Tự động lấy userId nếu không được cung cấp
    if not userId:
        userId = _extract_user_id_from_message()
        if not userId:
            return {
                "error": "userId is required",
                "message": "Please provide userId parameter or include it in your message (e.g., 'User ID của mình là demo')",
                "suggestion": "Include userId in your request or provide it as a parameter",
            }

    if type not in ["buy", "sell"]:
        return {"error": "type must be 'buy' or 'sell'", "type": type}

    if orderType not in ["limit", "market"]:
        return {
            "error": "orderType must be 'limit' or 'market'",
            "orderType": orderType,
        }

    payload = {
        "userId": userId,
        "symbol": symbol.upper(),
        "type": type,
        "quantity": quantity,
        "price": price,
        "orderType": orderType,
    }

    return _call_backend_api("POST", "stock-transactions/transactions", data=payload)


def get_transaction_history(userId: Optional[str] = None) -> Dict[str, Any]:
    """
    Lấy lịch sử giao dịch của user.

    Args:
        userId: ID người dùng (optional - sẽ tự động lấy từ context nếu không có)

    Returns:
        Dict chứa danh sách giao dịch hoặc error

    Example:
        >>> result = get_transaction_history()
        >>> transactions = result.get("metadata", [])
    """
    # Tự động lấy userId nếu không được cung cấp
    if not userId:
        userId = _extract_user_id_from_message()
        if not userId:
            return {
                "error": "userId is required",
                "message": "Please provide userId parameter or include it in your message",
                "suggestion": "Include userId in your request (e.g., 'User ID của mình là demo')",
            }

    return _call_backend_api("GET", f"stock-transactions/transactions/{userId}")


def get_transaction_stats(userId: Optional[str] = None) -> Dict[str, Any]:
    """
    Lấy thống kê giao dịch của user.

    Args:
        userId: ID người dùng (optional - sẽ tự động lấy từ context nếu không có)

    Returns:
        Dict chứa thống kê (totalProfit, totalTransactions, winRate, etc.) hoặc error

    Example:
        >>> result = get_transaction_stats()
        >>> stats = result.get("metadata", {})
        >>> print(stats.get("totalProfit"))
    """
    # Tự động lấy userId nếu không được cung cấp
    if not userId:
        userId = _extract_user_id_from_message()
        if not userId:
            return {
                "error": "userId is required",
                "message": "Please provide userId parameter or include it in your message",
                "suggestion": "Include userId in your request (e.g., 'User ID của mình là demo')",
            }

    return _call_backend_api(
        "GET", f"stock-transactions/transactions/{userId}/stats", require_auth=True
    )


def get_user_profile(userId: Optional[str] = None) -> Dict[str, Any]:
    """
    Lấy thông tin profile của user.

    Args:
        userId: ID người dùng (optional - sẽ tự động lấy từ context nếu không có)

    Returns:
        Dict chứa thông tin user (fullName, email, balance, etc.) hoặc error

    Example:
        >>> result = get_user_profile()
        >>> profile = result.get("metadata", {})
        >>> print(profile.get("balance"))
    """
    # Tự động lấy userId nếu không được cung cấp
    if not userId:
        userId = _extract_user_id_from_message()
        if not userId:
            return {
                "error": "userId is required",
                "message": "Please provide userId parameter or include it in your message",
                "suggestion": "Include userId in your request (e.g., 'User ID của mình là demo')",
            }

    # Note: API yêu cầu Bearer token theo docs
    return _call_backend_api(
        "GET", "user/profile", params={"userId": userId}, require_auth=True
    )


def get_ranking() -> Dict[str, Any]:
    """
    Lấy bảng xếp hạng người dùng theo lợi nhuận.

    Returns:
        Dict chứa danh sách ranking hoặc error

    Example:
        >>> result = get_ranking()
        >>> rankings = result.get("metadata", [])
    """
    return _call_backend_api("GET", "stock-transactions/ranking")


def get_transaction_by_id(transactionId: str) -> Dict[str, Any]:
    """
    Lấy thông tin chi tiết một giao dịch theo ID.

    Args:
        transactionId: ID giao dịch

    Returns:
        Dict chứa thông tin giao dịch hoặc error

    Example:
        >>> result = get_transaction_by_id("trans_123456")
        >>> transaction = result.get("metadata", {})
    """
    return _call_backend_api(
        "GET", f"stock-transactions/transactions/{transactionId}", require_auth=True
    )


def cancel_transaction(transactionId: str) -> Dict[str, Any]:
    """
    Hủy một giao dịch.

    Args:
        transactionId: ID giao dịch cần hủy

    Returns:
        Dict chứa kết quả hủy giao dịch hoặc error

    Example:
        >>> result = cancel_transaction("trans_123456")
        >>> print(result.get("message"))
    """
    return _call_backend_api(
        "PUT",
        f"stock-transactions/transactions/{transactionId}/cancel",
        require_auth=True,
    )


def get_market_data(date: Optional[str] = None) -> Dict[str, Any]:
    """
    Lấy dữ liệu thị trường từ cache (VN-Index, HNX-Index, stocks).

    Args:
        date: Ngày cần lấy (format: YYYY-MM-DD). Nếu không có, lấy ngày mới nhất.

    Returns:
        Dict chứa dữ liệu thị trường hoặc error

    Example:
        >>> result = get_market_data()
        >>> vn30 = result.get("metadata", {}).get("vn30")
    """
    params = {}
    if date:
        params["date"] = date

    return _call_backend_api("GET", "market", params=params)


def get_stock_data(symbol: str, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Lấy dữ liệu cổ phiếu từ cache.

    Args:
        symbol: Mã cổ phiếu (ví dụ: "VCB", "VNM")
        date: Ngày cần lấy (format: YYYY-MM-DD). Nếu không có, lấy ngày mới nhất.

    Returns:
        Dict chứa dữ liệu cổ phiếu hoặc error

    Example:
        >>> result = get_stock_data("VCB")
        >>> price = result.get("metadata", {}).get("price")
    """
    params = {}
    if date:
        params["date"] = date

    return _call_backend_api("GET", f"market/stock/{symbol.upper()}", params=params)


def get_all_stocks(date: Optional[str] = None) -> Dict[str, Any]:
    """
    Lấy tất cả cổ phiếu từ cache.

    Args:
        date: Ngày cần lấy (format: YYYY-MM-DD). Nếu không có, lấy ngày mới nhất.

    Returns:
        Dict chứa danh sách cổ phiếu hoặc error

    Example:
        >>> result = get_all_stocks()
        >>> stocks = result.get("metadata", {}).get("stocks", [])
    """
    params = {}
    if date:
        params["date"] = date

    return _call_backend_api("GET", "market/stocks", params=params)


def get_vn30_history(days: int = 30) -> Dict[str, Any]:
    """
    Lấy lịch sử chỉ số VN30.

    Args:
        days: Số ngày cần lấy (default: 30)

    Returns:
        Dict chứa lịch sử VN30 hoặc error

    Example:
        >>> result = get_vn30_history(days=7)
        >>> history = result.get("metadata", {}).get("history", [])
    """
    return _call_backend_api("GET", "market/history/vn30", params={"days": days})
