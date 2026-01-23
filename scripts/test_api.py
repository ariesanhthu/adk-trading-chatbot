import asyncio
import json
import os
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

load_dotenv()

# BASE_URL = "https://adk-trading-chatbot.onrender.com"
BASE_URL = "https://arischi05-adk-trading-stock.hf.space"
# BASE_URL = "http://localhost:8002"  # Khớp với port được expose trong docker-compose
HEALTH_ENDPOINT = f"{BASE_URL}/health"
CHAT_ENDPOINT = f"{BASE_URL}/api/v1/chat"

HF_TOKEN = os.getenv("HF_TOKEN")

# Các payload mẫu để kích hoạt intent phổ biến
CHAT_SAMPLES: List[Dict[str, Any]] = [
    # === THÔNG TIN THỊ TRƯỜNG ===
    {
        "name": "market_overview",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Cho mình xem tổng quan thị trường hôm nay.",
                }
            ],
            "meta": {"user_id": "demo", "session_id": "sess-market"},
        },
    },
    {
        "name": "price_query",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Giá cổ phiếu VCB hôm nay là bao nhiêu?",
                }
            ],
            "meta": {"user_id": "demo", "session_id": "sess-price"},
        },
    },
    {
        "name": "price_query_multiple",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Cho mình biết giá của VCB, VNM và MWG hôm nay.",
                }
            ],
            "meta": {"user_id": "demo", "session_id": "sess-price-multi"},
        },
    },
    {
        "name": "news",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Có tin tức gì về VNM không?",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-news"},
        },
    },
    {
        "name": "stock_detail",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Cho mình xem chi tiết cổ phiếu MWG.",
                }
            ],
            "meta": {"user_id": "demo", "session_id": "sess-detail"},
        },
    },
    # === MUA/BÁN CỔ PHIẾU ===
    {
        "name": "buy_stock_incomplete",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Mình muốn mua cổ phiếu MWG, hướng dẫn giúp mình.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-buy-incomplete"},
        },
    },
    {
        "name": "buy_stock_complete",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Mình muốn mua 100 cổ phiếu MWG với giá 125,000 VNĐ. User ID của mình là demo.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-buy-complete"},
        },
    },
    {
        "name": "sell_stock_incomplete",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Mình muốn bán cổ phiếu VCB.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-sell-incomplete"},
        },
    },
    {
        "name": "sell_stock_complete",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Mình muốn bán 200 cổ phiếu VCB với giá 95,000 VNĐ. User ID của mình là demo.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-sell-complete"},
        },
    },
    # === THÔNG TIN CÁ NHÂN ===
    {
        "name": "user_profile",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Cho mình xem thông tin tài khoản. User ID của mình là demo.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-profile"},
        },
    },
    {
        "name": "transaction_history",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Cho mình xem lịch sử giao dịch. User ID của mình là demo.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-history"},
        },
    },
    {
        "name": "transaction_stats",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Cho mình xem thống kê giao dịch. User ID của mình là demo.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-stats"},
        },
    },
    {
        "name": "ranking",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Cho mình xem bảng xếp hạng người dùng.",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-ranking"},
        },
    },
    # === TEST CONVERSATION FLOW ===
    {
        "name": "buy_flow_step1",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Mình muốn mua cổ phiếu VCB",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-buy-flow"},
        },
    },
    {
        "name": "buy_flow_step2",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Mình muốn mua cổ phiếu VCB",
                },
                {
                    "role": "assistant",
                    "content": "Tôi sẽ hướng dẫn bạn mua cổ phiếu VCB. Giá hiện tại là 95,000 VNĐ. Vui lòng điền form bên dưới.",
                },
                {
                    "role": "user",
                    "content": "Xác nhận mua VCB",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-buy-flow"},
        },
    },
    {
        "name": "sell_flow_step1",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Mình muốn bán cổ phiếu MWG",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-sell-flow"},
        },
    },
    {
        "name": "sell_flow_step2",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Mình muốn bán cổ phiếu MWG",
                },
                {
                    "role": "assistant",
                    "content": "Tôi sẽ hướng dẫn bạn bán cổ phiếu MWG. Bạn đang có 500 cổ phiếu. Vui lòng điền form bên dưới.",
                },
                {
                    "role": "user",
                    "content": "Xác nhận bán MWG",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-sell-flow"},
        },
    },
    {
        "name": "conversation_with_history",
        "payload": {
            "messages": [
                {
                    "role": "user",
                    "content": "Giá VCB hôm nay?",
                },
                {
                    "role": "assistant",
                    "content": "Giá VCB hôm nay là 95,000 VNĐ, tăng 2.5% so với hôm qua.",
                },
                {
                    "role": "user",
                    "content": "Cho mình xem lịch sử giá VCB",
                },
            ],
            "meta": {"user_id": "demo", "session_id": "sess-history-flow"},
        },
    },
]


async def check_health(client: httpx.AsyncClient, retries: int = 5) -> None:
    for attempt in range(1, retries + 1):
        try:
            headers = {}
            if HF_TOKEN:
                headers["Authorization"] = f"Bearer {HF_TOKEN}"

            resp = await client.get(HEALTH_ENDPOINT, headers=headers)
            resp.raise_for_status()
            print("✅ /health:", resp.json())
            return
        except httpx.HTTPError as exc:
            if attempt == retries:
                raise
            print(f"[retry {attempt}/{retries}] /health fail: {exc}. Đợi 1s...")
            await asyncio.sleep(1)


def _check_market_data_in_reply(reply: str) -> Dict[str, Any]:
    """Kiểm tra xem reply có chứa dữ liệu từ thị trường không."""
    checks = {
        "has_price": False,
        "has_number": False,
        "has_symbol": False,
        "has_market_keywords": False,
        "has_data": False,
    }

    reply_lower = reply.lower()

    # Kiểm tra có số (giá, điểm số, %)
    import re

    numbers = re.findall(r"\d+[.,]?\d*", reply)
    checks["has_number"] = len(numbers) > 0

    # Kiểm tra có mã cổ phiếu (3-4 chữ cái in hoa)
    symbols = re.findall(r"\b([A-Z]{3,4})\b", reply)
    checks["has_symbol"] = len(symbols) > 0

    # Kiểm tra có từ khóa về giá
    price_keywords = ["giá", "price", "vnđ", "đồng", "điểm", "vn-index", "hnx"]
    checks["has_price"] = any(kw in reply_lower for kw in price_keywords)

    # Kiểm tra có từ khóa về thị trường
    market_keywords = [
        "thị trường",
        "market",
        "tăng",
        "giảm",
        "đóng cửa",
        "mở cửa",
        "chỉ số",
    ]
    checks["has_market_keywords"] = any(kw in reply_lower for kw in market_keywords)

    # Tổng hợp: có dữ liệu nếu có số hoặc từ khóa thị trường
    checks["has_data"] = checks["has_number"] or checks["has_market_keywords"]

    return checks


async def test_chat_samples(client: httpx.AsyncClient) -> None:
    """Test các chat samples và kiểm tra response."""
    results = []

    for sample in CHAT_SAMPLES:
        name = sample["name"]
        payload = sample["payload"]
        print(f"\n{'='*60}")
        print(f"=== Test chat: {name} ===")
        print(f"{'='*60}")

        try:
            headers = {}
            if HF_TOKEN:
                headers["Authorization"] = f"Bearer {HF_TOKEN}"
            
            resp = await client.post(CHAT_ENDPOINT, json=payload, headers=headers, timeout=60.0)
            print(f"Status: {resp.status_code}")

            if resp.status_code != 200:
                print(f"❌ Error Body: {resp.text[:500]}")
                results.append(
                    {
                        "name": name,
                        "status": "error",
                        "status_code": resp.status_code,
                    }
                )
                continue

            data = resp.json()
            reply = data.get("reply", "")
            ui_effects = data.get("ui_effects", [])
            suggestions = data.get("suggestion_messages", [])
            raw_output = data.get("raw_agent_output", {})

            # Kiểm tra reply
            print(f"\n📝 Reply ({len(reply)} chars):")
            print(f"   {reply[:200]}{'...' if len(reply) > 200 else ''}")

            # Kiểm tra dữ liệu thị trường trong reply
            market_checks = _check_market_data_in_reply(reply)
            print(f"\n📊 Market Data Check:")
            for key, value in market_checks.items():
                icon = "✅" if value else "❌"
                print(f"   {icon} {key}: {value}")

            if not market_checks["has_data"] and name in [
                "market_overview",
                "price_query",
                "price_query_multiple",
                "news",
            ]:
                print(f"   ⚠️  WARNING: Không có dữ liệu thị trường trong reply!")
                print(
                    f"   💡 Có thể agent không gọi MCP tools hoặc không trả về dữ liệu"
                )

            # Kiểm tra UI Effects
            print(f"\n🎨 UI Effects ({len(ui_effects)}):")
            if ui_effects:
                try:
                    print(json.dumps(ui_effects, ensure_ascii=False, indent=2))
                except Exception as e:
                    print(f"   ❌ Error formatting UI effects: {e}")
                    print(f"   Raw: {ui_effects}")
            else:
                print("   (không có)")

            # Kiểm tra Suggestions
            print(f"\n💡 Suggestions ({len(suggestions)}):")
            if suggestions:
                for i, sug in enumerate(suggestions, 1):
                    action = sug.get("action", "")
                    print(
                        f"   {i}. {sug.get('text', 'N/A')} ({sug.get('icon', '')}) - action: {action}"
                    )
            else:
                print("   (không có)")

            # Kiểm tra conversation history trong payload
            if len(payload.get("messages", [])) > 1:
                print(
                    f"\n📜 Conversation History ({len(payload['messages'])} messages):"
                )
                for i, msg in enumerate(payload["messages"], 1):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")[:100]
                    print(f"   {i}. [{role}]: {content}...")

            # Kiểm tra raw agent output (debug)
            if raw_output:
                events = raw_output.get("events", [])
                print(f"\n🔍 Raw Agent Output:")
                print(f"   Events: {len(events)}")
                if events:
                    # Tìm events có text từ model
                    model_events = [
                        e
                        for e in events
                        if e.get("author") == "model" and e.get("text")
                    ]
                    print(f"   Model events with text: {len(model_events)}")
                    if model_events:
                        print(
                            f"   First model event text: {model_events[0].get('text', '')[:100]}"
                        )

            # Đánh giá kết quả
            status = "ok"
            issues = []

            if not reply or len(reply.strip()) < 10:
                status = "warning"
                issues.append("Reply quá ngắn hoặc rỗng")

            if name in [
                "market_overview",
                "price_query",
                "price_query_multiple",
                "news",
            ]:
                if not market_checks["has_data"]:
                    status = "warning"
                    issues.append("Không có dữ liệu thị trường trong reply")

            if name in [
                "buy_stock_incomplete",
                "buy_stock_complete",
                "sell_stock_incomplete",
                "sell_stock_complete",
            ]:
                if not ui_effects:
                    status = "warning"
                    issues.append("Không có UI effects cho mua/bán")
                else:
                    # Kiểm tra có OPEN_BUY_STOCK hoặc OPEN_SELL_STOCK không
                    has_buy_sell = any(
                        eff.get("type") in ["OPEN_BUY_STOCK", "OPEN_SELL_STOCK"]
                        for eff in ui_effects
                    )
                    if not has_buy_sell:
                        status = "warning"
                        issues.append(
                            "Không có UI effect OPEN_BUY_STOCK hoặc OPEN_SELL_STOCK"
                        )

            # Kiểm tra suggestions dựa trên flow state
            if name in ["buy_flow_step1", "sell_flow_step1"]:
                # Bước 1: Nên có suggestions về xác nhận/hủy
                has_confirm = any(
                    "xác nhận" in sug.get("text", "").lower()
                    or "confirm" in sug.get("action", "").lower()
                    for sug in suggestions
                )
                if not has_confirm and ui_effects:
                    # Nếu có UI effect nhưng không có suggestion confirm, có thể là warning
                    has_ui_buy_sell = any(
                        eff.get("type") in ["OPEN_BUY_STOCK", "OPEN_SELL_STOCK"]
                        for eff in ui_effects
                    )
                    if has_ui_buy_sell:
                        status = "warning"
                        issues.append(
                            "Có UI effect mua/bán nhưng không có suggestion xác nhận"
                        )

            if name in ["buy_flow_step2", "sell_flow_step2"]:
                # Bước 2: Sau khi xác nhận, nên có suggestions về lịch sử giao dịch
                has_history = any(
                    "lịch sử" in sug.get("text", "").lower()
                    or "giao dịch" in sug.get("text", "").lower()
                    for sug in suggestions
                )
                if not has_history:
                    # Không bắt buộc, chỉ log
                    print(
                        "   💡 Note: Không có suggestion về lịch sử giao dịch sau xác nhận"
                    )

            # Kiểm tra suggestions dựa trên conversation history
            if name == "conversation_with_history":
                # Nên có suggestions liên quan đến VCB (symbol từ conversation)
                has_vcb_suggestion = any(
                    "VCB" in sug.get("text", "") or "VCB" in sug.get("action", "")
                    for sug in suggestions
                )
                if not has_vcb_suggestion:
                    print(
                        "   💡 Note: Suggestions không có context từ conversation history (VCB)"
                    )

            results.append(
                {
                    "name": name,
                    "status": status,
                    "status_code": resp.status_code,
                    "reply_length": len(reply),
                    "ui_effects_count": len(ui_effects),
                    "suggestions_count": len(suggestions),
                    "market_data": market_checks,
                    "issues": issues,
                }
            )

            if issues:
                print(f"\n⚠️  Issues:")
                for issue in issues:
                    print(f"   - {issue}")

        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback

            traceback.print_exc()
            results.append(
                {
                    "name": name,
                    "status": "error",
                    "error": str(e),
                }
            )

    # Tổng kết
    print(f"\n{'='*60}")
    print("=== TỔNG KẾT ===")
    print(f"{'='*60}")

    total = len(results)
    ok = len([r for r in results if r.get("status") == "ok"])
    warning = len([r for r in results if r.get("status") == "warning"])
    error = len([r for r in results if r.get("status") == "error"])

    print(f"Tổng số test: {total}")
    print(f"✅ OK: {ok}")
    print(f"⚠️  Warning: {warning}")
    print(f"❌ Error: {error}")

    if warning > 0:
        print(f"\n⚠️  Tests có warning:")
        for r in results:
            if r.get("status") == "warning":
                print(f"   - {r['name']}: {', '.join(r.get('issues', []))}")

    if error > 0:
        print(f"\n❌ Tests có error:")
        for r in results:
            if r.get("status") == "error":
                print(f"   - {r['name']}: {r.get('error', 'Unknown error')}")


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        await check_health(client)
        await test_chat_samples(client)


if __name__ == "__main__":
    asyncio.run(main())
