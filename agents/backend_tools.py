"""
Backend API Tools cho Agent - Gọi các API backend để thực hiện giao dịch và lấy thông tin.

Agent có thể sử dụng các tools này để:
- Tạo giao dịch mua/bán cổ phiếu (POST)
- Lấy lịch sử giao dịch (GET)
- Lấy thống kê giao dịch (GET)
- Lấy thông tin user profile (GET)
- Lấy bảng xếp hạng (GET)
"""

import json
import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()

# Backend API base URL từ .env
BE_API_BASE = os.getenv("BE_API", "").strip()
if not BE_API_BASE:
    print("Warning: BE_API not found in .env. Backend tools will not work.")

# Authentication token (optional - chỉ cần cho các endpoint có auth)
BE_API_TOKEN = os.getenv("BE_API_TOKEN", "").strip()

# Timeout cho HTTP requests
HTTP_TIMEOUT = 30.0


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
    userId: str,
    symbol: str,
    type: str,  # "buy" hoặc "sell"
    quantity: int,
    price: float,
    orderType: str = "limit",  # "limit" hoặc "market"
) -> Dict[str, Any]:
    """
    Tạo giao dịch mua/bán cổ phiếu.

    Args:
        userId: ID người dùng
        symbol: Mã cổ phiếu (ví dụ: "MWG", "VCB")
        type: Loại giao dịch ("buy" hoặc "sell")
        quantity: Số lượng cổ phiếu
        price: Giá đặt lệnh (VNĐ)
        orderType: Loại lệnh ("limit" hoặc "market", default: "limit")

    Returns:
        Dict chứa thông tin giao dịch đã tạo hoặc error

    Example:
        >>> result = create_transaction(
        ...     userId="69293046bcbc4ea01b8b76ce",
        ...     symbol="MWG",
        ...     type="buy",
        ...     quantity=100,
        ...     price=125000,
        ...     orderType="limit"
        ... )
        >>> print(result.get("metadata", {}).get("transactionId"))
    """
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


def get_transaction_history(userId: str) -> Dict[str, Any]:
    """
    Lấy lịch sử giao dịch của user.

    Args:
        userId: ID người dùng

    Returns:
        Dict chứa danh sách giao dịch hoặc error

    Example:
        >>> result = get_transaction_history("69293046bcbc4ea01b8b76ce")
        >>> transactions = result.get("metadata", [])
    """
    return _call_backend_api("GET", f"stock-transactions/transactions/{userId}")


def get_transaction_stats(userId: str) -> Dict[str, Any]:
    """
    Lấy thống kê giao dịch của user.

    Args:
        userId: ID người dùng

    Returns:
        Dict chứa thống kê (totalProfit, totalTransactions, winRate, etc.) hoặc error

    Example:
        >>> result = get_transaction_stats("69293046bcbc4ea01b8b76ce")
        >>> stats = result.get("metadata", {})
        >>> print(stats.get("totalProfit"))
    """
    return _call_backend_api(
        "GET", f"stock-transactions/transactions/{userId}/stats", require_auth=True
    )


def get_user_profile(userId: str) -> Dict[str, Any]:
    """
    Lấy thông tin profile của user.

    Args:
        userId: ID người dùng

    Returns:
        Dict chứa thông tin user (fullName, email, balance, etc.) hoặc error

    Example:
        >>> result = get_user_profile("69293046bcbc4ea01b8b76ce")
        >>> profile = result.get("metadata", {})
        >>> print(profile.get("balance"))
    """
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
