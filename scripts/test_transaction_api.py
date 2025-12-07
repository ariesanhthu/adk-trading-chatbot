"""Script test các API giao dịch backend (POST transactions, GET history, stats, etc.)."""

import asyncio
import json
import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()

# Backend API base URL
BE_API_BASE = os.getenv("BE_API", "").strip()
if not BE_API_BASE:
    print("❌ Error: BE_API not found in .env file")
    exit(1)

# Authentication token (optional - chỉ cần cho các endpoint có auth)
BE_API_TOKEN = os.getenv("BE_API_TOKEN", "").strip()
if BE_API_TOKEN:
    print(f"✅ Authentication token found (length: {len(BE_API_TOKEN)})\n")
else:
    print(
        "⚠️  No authentication token found (BE_API_TOKEN). Some endpoints may require auth.\n"
    )

print(f"✅ Backend API Base URL: {BE_API_BASE}\n")

# Test data
TEST_USER_ID = "69293046bcbc4ea01b8b76ce"  # User ID mẫu
TEST_SYMBOL = "MWG"
TEST_QUANTITY = 100
TEST_PRICE = 125000.0


async def test_create_transaction(client: httpx.AsyncClient) -> None:
    """Test POST /stock-transactions/transactions - Tạo giao dịch mua."""
    print("=" * 60)
    print("TEST 1: POST /stock-transactions/transactions (Mua cổ phiếu)")
    print("=" * 60)

    url = f"{BE_API_BASE.rstrip('/')}/stock-transactions/transactions"
    payload = {
        "userId": TEST_USER_ID,
        "symbol": TEST_SYMBOL,
        "type": "buy",
        "quantity": TEST_QUANTITY,
        "price": TEST_PRICE,
        "orderType": "limit",
    }

    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    print()

    # Thử HTTPS trước, nếu fail với SSL error thì thử HTTP
    urls_to_try = [url]
    if url.startswith("https://"):
        http_url = url.replace("https://", "http://", 1)
        urls_to_try.append(http_url)

    last_error = None
    for try_url in urls_to_try:
        try:
            # httpx.AsyncClient không hỗ trợ verify parameter trong request methods
            # SSL verification đã được cấu hình khi tạo client (verify=False)
            resp = await client.post(try_url, json=payload, timeout=30.0)
            print(f"Status Code: {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                print("✅ Success!")
                if try_url != url:
                    print(f"⚠️  Note: Used HTTP instead of HTTPS (URL: {try_url})")
                print("Response:")
                print(json.dumps(data, ensure_ascii=False, indent=2))

                # Lưu transactionId để test tiếp
                metadata = data.get("metadata", {})
                transaction_id = metadata.get("transactionId") or metadata.get("_id")
                if transaction_id:
                    print(f"\n💾 Transaction ID: {transaction_id}")
                    return transaction_id
            else:
                print(f"❌ Error: {resp.status_code}")
                print("Response:", resp.text)
                return None

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            error_msg = str(e)
            if "SSL" in error_msg or "wrong version number" in error_msg.lower():
                # SSL error - thử HTTP nếu chưa thử
                if try_url == url and url.startswith("https://"):
                    print(f"⚠️  HTTPS failed with SSL error, trying HTTP...")
                    last_error = e
                    continue
            # Nếu đã thử cả 2 URL
            if try_url == urls_to_try[-1]:
                print(f"❌ Request Error: {e}")
                if "SSL" in error_msg or "wrong version number" in error_msg.lower():
                    print(
                        "💡 Suggestion: Backend server might be using HTTP. Try changing BE_API from 'https://' to 'http://' in .env"
                    )
                last_error = e
                break

        except httpx.RequestError as e:
            if try_url == urls_to_try[-1]:
                print(f"❌ Request Error: {e}")
                last_error = e
            else:
                last_error = e
                continue

        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            last_error = e
            break

    return None


async def _make_request_with_fallback(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    require_auth: bool = False,
    **kwargs,
) -> Optional[httpx.Response]:
    """
    Helper function để thử HTTPS trước, nếu fail thì thử HTTP.

    Args:
        client: httpx async client
        method: HTTP method (GET, POST, PUT, DELETE)
        url: Request URL
        require_auth: Nếu True, sẽ thêm Authorization header nếu có token
        **kwargs: Additional arguments cho httpx request
    """
    urls_to_try = [url]
    if url.startswith("https://"):
        http_url = url.replace("https://", "http://", 1)
        urls_to_try.append(http_url)

    # Thêm Authorization header nếu cần
    headers = kwargs.get("headers", {})
    if require_auth and BE_API_TOKEN:
        headers["Authorization"] = f"Bearer {BE_API_TOKEN}"
        kwargs["headers"] = headers
    elif require_auth and not BE_API_TOKEN:
        print(
            "⚠️  Warning: This endpoint requires authentication but BE_API_TOKEN is not set in .env"
        )

    last_error = None
    for try_url in urls_to_try:
        try:
            # httpx.AsyncClient không hỗ trợ verify parameter trong request methods
            # Nếu cần disable SSL, phải tạo client mới với verify=False
            # Nhưng vì đã có fallback HTTP, nên chỉ cần gọi request bình thường
            if method.upper() == "GET":
                resp = await client.get(try_url, **kwargs)
            elif method.upper() == "POST":
                resp = await client.post(try_url, **kwargs)
            elif method.upper() == "PUT":
                resp = await client.put(try_url, **kwargs)
            elif method.upper() == "DELETE":
                resp = await client.delete(try_url, **kwargs)
            else:
                return None

            if try_url != url:
                print(f"⚠️  Note: Used HTTP instead of HTTPS")
            return resp

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            error_msg = str(e)
            if "SSL" in error_msg or "wrong version number" in error_msg.lower():
                if try_url == url and url.startswith("https://"):
                    last_error = e
                    continue
            if try_url == urls_to_try[-1]:
                last_error = e
                break

        except httpx.RequestError as e:
            if try_url == urls_to_try[-1]:
                last_error = e
                break
            last_error = e
            continue

    if last_error:
        error_msg = str(last_error)
        if "SSL" in error_msg or "wrong version number" in error_msg.lower():
            print(
                f"💡 Suggestion: Backend might be using HTTP. Try changing BE_API from 'https://' to 'http://' in .env"
            )
    raise last_error if last_error else Exception("Request failed")


async def test_create_sell_transaction(client: httpx.AsyncClient) -> None:
    """Test POST /stock-transactions/transactions - Tạo giao dịch bán."""
    print("\n" + "=" * 60)
    print("TEST 2: POST /stock-transactions/transactions (Bán cổ phiếu)")
    print("=" * 60)

    url = f"{BE_API_BASE.rstrip('/')}/stock-transactions/transactions"
    payload = {
        "userId": TEST_USER_ID,
        "symbol": "VCB",
        "type": "sell",
        "quantity": 50,
        "price": 95000.0,
        "orderType": "limit",
    }

    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    print()

    try:
        resp = await _make_request_with_fallback(
            client, "POST", url, json=payload, timeout=30.0
        )
        print(f"Status Code: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print("✅ Success!")
            print("Response:")
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(f"❌ Error: {resp.status_code}")
            print("Response:", resp.text)

    except Exception as e:
        print(f"❌ Request Error: {e}")


async def test_get_transaction_history(client: httpx.AsyncClient) -> None:
    """Test GET /stock-transactions/transactions/:userId - Lấy lịch sử giao dịch."""
    print("\n" + "=" * 60)
    print("TEST 3: GET /stock-transactions/transactions/:userId")
    print("=" * 60)

    url = f"{BE_API_BASE.rstrip('/')}/stock-transactions/transactions/{TEST_USER_ID}"

    print(f"URL: {url}")
    print()

    try:
        resp = await _make_request_with_fallback(client, "GET", url, timeout=30.0)
        print(f"Status Code: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print("✅ Success!")
            print("Response:")
            print(json.dumps(data, ensure_ascii=False, indent=2))

            # Đếm số giao dịch
            metadata = data.get("metadata", [])
            if isinstance(metadata, list):
                print(f"\n📊 Total transactions: {len(metadata)}")
        else:
            print(f"❌ Error: {resp.status_code}")
            print("Response:", resp.text)

    except Exception as e:
        print(f"❌ Request Error: {e}")


async def test_get_transaction_stats(client: httpx.AsyncClient) -> None:
    """Test GET /stock-transactions/transactions/:userId/stats - Lấy thống kê."""
    print("\n" + "=" * 60)
    print("TEST 4: GET /stock-transactions/transactions/:userId/stats")
    print("=" * 60)

    url = f"{BE_API_BASE.rstrip('/')}/stock-transactions/transactions/{TEST_USER_ID}/stats"

    print(f"URL: {url}")
    print("⚠️  Note: This endpoint requires authentication (Auth: ✅)")
    print()

    try:
        resp = await _make_request_with_fallback(
            client, "GET", url, require_auth=True, timeout=30.0
        )
        print(f"Status Code: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print("✅ Success!")
            print("Response:")
            print(json.dumps(data, ensure_ascii=False, indent=2))

            # Hiển thị thống kê chính
            metadata = data.get("metadata", {})
            if isinstance(metadata, dict):
                print("\n📊 Statistics Summary:")
                print(f"  - Total Profit: {metadata.get('totalProfit', 'N/A')}")
                print(
                    f"  - Total Transactions: {metadata.get('totalTransactions', 'N/A')}"
                )
                print(f"  - Win Rate: {metadata.get('winRate', 'N/A')}")
        else:
            print(f"❌ Error: {resp.status_code}")
            print("Response:", resp.text)

    except Exception as e:
        print(f"❌ Request Error: {e}")


async def test_get_user_profile(client: httpx.AsyncClient) -> None:
    """Test GET /user/profile - Lấy thông tin user."""
    print("\n" + "=" * 60)
    print("TEST 5: GET /user/profile")
    print("=" * 60)

    url = f"{BE_API_BASE.rstrip('/')}/user/profile"
    params = {"userId": TEST_USER_ID}

    print(f"URL: {url}")
    print(f"Params: {params}")
    print("⚠️  Note: This endpoint requires authentication (Auth: ✅)")
    print()

    try:
        resp = await _make_request_with_fallback(
            client, "GET", url, require_auth=True, params=params, timeout=30.0
        )
        print(f"Status Code: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print("✅ Success!")
            print("Response:")
            print(json.dumps(data, ensure_ascii=False, indent=2))

            # Hiển thị thông tin chính
            metadata = data.get("metadata", {})
            if isinstance(metadata, dict):
                print("\n👤 User Profile Summary:")
                print(f"  - Name: {metadata.get('user_fullName', 'N/A')}")
                print(f"  - Email: {metadata.get('email', 'N/A')}")
                print(f"  - Balance: {metadata.get('balance', 'N/A')}")
        else:
            print(f"❌ Error: {resp.status_code}")
            print("Response:", resp.text)

    except Exception as e:
        print(f"❌ Request Error: {e}")


async def test_get_ranking(client: httpx.AsyncClient) -> None:
    """Test GET /stock-transactions/ranking - Lấy bảng xếp hạng."""
    print("\n" + "=" * 60)
    print("TEST 6: GET /stock-transactions/ranking")
    print("=" * 60)

    url = f"{BE_API_BASE.rstrip('/')}/stock-transactions/ranking"

    print(f"URL: {url}")
    print()

    try:
        resp = await _make_request_with_fallback(client, "GET", url, timeout=30.0)
        print(f"Status Code: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print("✅ Success!")
            print("Response:")
            print(json.dumps(data, ensure_ascii=False, indent=2))

            # Hiển thị top 5
            metadata = data.get("metadata", [])
            if isinstance(metadata, list):
                print(f"\n🏆 Top 5 Rankings:")
                for i, item in enumerate(metadata[:5], 1):
                    print(
                        f"  {i}. {item.get('user_fullName', 'N/A')} - "
                        f"Profit: {item.get('profit', 'N/A')}"
                    )
        else:
            print(f"❌ Error: {resp.status_code}")
            print("Response:", resp.text)

    except Exception as e:
        print(f"❌ Request Error: {e}")


async def main() -> None:
    """Chạy tất cả các test."""
    print("🚀 Starting Backend API Tests\n")

    # Tạo client với verify=False để tránh SSL errors (cho development)
    # Nếu backend dùng HTTPS với SSL hợp lệ, có thể set verify=True
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        # Test 1: Tạo giao dịch mua
        transaction_id = await test_create_transaction(client)

        # Test 2: Tạo giao dịch bán
        await test_create_sell_transaction(client)

        # Test 3: Lấy lịch sử giao dịch
        await test_get_transaction_history(client)

        # Test 4: Lấy thống kê
        await test_get_transaction_stats(client)

        # Test 5: Lấy user profile
        await test_get_user_profile(client)

        # Test 6: Lấy ranking
        await test_get_ranking(client)

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
