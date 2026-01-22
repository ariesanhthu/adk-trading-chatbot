"""Chat endpoint for chatbot API."""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..deps import get_agent
from ...schemas.chat import ChatRequest, ChatResponse, SuggestionMessage
from ...schemas.ui import (
    ShowMarketOverviewInstruction,
    OpenBuyStockInstruction,
    OpenSellStockInstruction,
    OpenNewsInstruction,
    OpenStockDetailInstruction,
    ConfirmTransactionInstruction,
    ShowUserProfileInstruction,
    ShowTransactionHistoryInstruction,
    ShowTransactionStatsInstruction,
    ShowRankingInstruction,
    FeatureInstruction,
    BuyStockData,
    SellStockData,
    TransactionData,
    UserProfileData,
    TransactionHistoryData,
    TransactionStatsData,
    RankingData,
    BuyFlowStep,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def _extract_intent_from_reply(reply: str, agent_output: dict) -> str:
    """Extract intent from agent reply or output."""
    # Kiểm tra agent_output trước
    if isinstance(agent_output, dict):
        intent = agent_output.get("intent")
        if intent:
            return intent

    # Nếu không có intent trong output, thử parse từ reply
    reply_lower = reply.lower()
    if (
        "tổng quan" in reply_lower
        or "market overview" in reply_lower
        or "thị trường" in reply_lower
    ):
        return "show_market_overview"
    elif "mua" in reply_lower or "buy" in reply_lower:
        return "buy_stock"
    elif "tin tức" in reply_lower or "news" in reply_lower:
        return "view_news"
    elif (
        "chi tiết" in reply_lower
        or "detail" in reply_lower
        or "thông tin" in reply_lower
    ):
        return "stock_detail"

    return None


def _build_ui_effects(
    intent: str, agent_output: dict, reply: str
) -> list[FeatureInstruction]:
    """Build UI effects from agent intent and output."""
    ui_effects: list[FeatureInstruction] = []

    if intent == "show_market_overview":
        ui_effects.append(ShowMarketOverviewInstruction())

    elif intent == "buy_stock":
        symbol = agent_output.get("symbol") or _extract_symbol_from_reply(reply)
        price = agent_output.get("price") or agent_output.get("currentPrice")

        if symbol and price:
            steps = agent_output.get(
                "steps",
                [
                    {"id": "choose_volume", "title": "Chọn khối lượng"},
                    {"id": "choose_price", "title": "Chọn giá đặt lệnh"},
                    {"id": "confirm", "title": "Xác nhận lệnh"},
                ],
            )

            step_models = [
                BuyFlowStep(**s) if isinstance(s, dict) else s for s in steps
            ]

            ui_effects.append(
                OpenBuyStockInstruction(
                    payload=BuyStockData(
                        symbol=symbol,
                        currentPrice=float(price),
                        steps=step_models,
                    )
                )
            )

    elif intent == "view_news":
        news_data = agent_output.get("news_data")
        if news_data:
            ui_effects.append(OpenNewsInstruction(payload=news_data))

    elif intent == "stock_detail":
        stock_detail = agent_output.get("stock_detail")
        if stock_detail:
            ui_effects.append(OpenStockDetailInstruction(payload=stock_detail))

    elif intent == "sell_stock":
        symbol = agent_output.get("symbol") or _extract_symbol_from_reply(reply)
        price = agent_output.get("price") or agent_output.get("currentPrice")
        available_qty = agent_output.get("availableQuantity", 0.0)

        if symbol:
            steps = agent_output.get(
                "steps",
                [
                    {"id": "choose_volume", "title": "Chọn khối lượng"},
                    {"id": "choose_price", "title": "Chọn giá đặt lệnh"},
                    {"id": "confirm", "title": "Xác nhận lệnh"},
                ],
            )

            step_models = [
                BuyFlowStep(**s) if isinstance(s, dict) else s for s in steps
            ]

            ui_effects.append(
                OpenSellStockInstruction(
                    payload=SellStockData(
                        symbol=symbol,
                        currentPrice=float(price) if price else 0.0,
                        availableQuantity=float(available_qty),
                        steps=step_models,
                    )
                )
            )

    elif intent == "user_profile":
        userId = agent_output.get("userId") or "current_user"
        ui_effects.append(
            ShowUserProfileInstruction(
                payload=UserProfileData(
                    userId=userId,
                    fullName=agent_output.get("fullName"),
                    email=agent_output.get("email"),
                    balance=agent_output.get("balance"),
                    avatar=agent_output.get("avatar"),
                )
            )
        )

    elif intent == "transaction_history":
        userId = agent_output.get("userId") or "current_user"
        transactions = agent_output.get("transactions", [])
        ui_effects.append(
            ShowTransactionHistoryInstruction(
                payload=TransactionHistoryData(
                    userId=userId,
                    transactions=transactions,
                )
            )
        )

    elif intent == "transaction_stats":
        userId = agent_output.get("userId") or "current_user"
        ui_effects.append(
            ShowTransactionStatsInstruction(
                payload=TransactionStatsData(
                    userId=userId,
                    totalProfit=agent_output.get("totalProfit"),
                    totalTransactions=agent_output.get("totalTransactions"),
                    winRate=agent_output.get("winRate"),
                )
            )
        )

    elif intent == "ranking":
        rankings = agent_output.get("rankings", [])
        userRank = agent_output.get("userRank")
        ui_effects.append(
            ShowRankingInstruction(
                payload=RankingData(
                    rankings=rankings,
                    userRank=userRank,
                )
            )
        )

    return ui_effects


def _extract_symbol_from_reply(reply: str) -> Optional[str]:
    """Extract stock symbol from reply text."""
    import re

    # Tìm mã chứng khoán (thường là 3-4 chữ cái in hoa)
    matches = re.findall(r"\b([A-Z]{3,4})\b", reply)
    if matches:
        return matches[0]
    return None


def _parse_ui_effects_from_reply(reply: str, query: str) -> list[FeatureInstruction]:
    """
    Parse agent reply để detect UI effects cần thiết

    Logic:
    - Nếu reply có số liệu giá → có thể show chart
    - Nếu reply có bảng dữ liệu → table
    - Nếu có so sánh nhiều mã → comparison
    """
    effects = []
    reply_lower = reply.lower()
    query_lower = query.lower()

    # Phát hiện nhu cầu xem tổng quan thị trường
    if any(
        kw in query_lower or kw in reply_lower
        for kw in ["tổng quan", "market overview", "thị trường chung"]
    ):
        effects.append(ShowMarketOverviewInstruction())

    # Phát hiện ý định mua cổ phiếu
    if any(kw in query_lower for kw in ["mua", "buy", "đặt lệnh"]):
        symbol = _extract_symbol_from_reply(reply) or _extract_symbol_from_reply(query)
        if symbol:
            # Hướng dẫn mua đơn giản - giá thực sẽ lấy từ agent
            effects.append(
                OpenBuyStockInstruction(
                    payload=BuyStockData(
                        symbol=symbol,
                        currentPrice=0.0,  # Placeholder, should be filled by agent
                        steps=[
                            BuyFlowStep(id="choose_volume", title="Chọn khối lượng"),
                            BuyFlowStep(id="choose_price", title="Chọn giá đặt lệnh"),
                            BuyFlowStep(id="confirm", title="Xác nhận lệnh"),
                        ],
                    )
                )
            )

    # Phát hiện yêu cầu xem tin tức
    if any(
        kw in query_lower or kw in reply_lower for kw in ["tin tức", "news", "sự kiện"]
    ):
        # Cần trích xuất dữ liệu tin tức từ agent
        pass

    # Phát hiện yêu cầu xem chi tiết cổ phiếu
    symbol = _extract_symbol_from_reply(query)
    if symbol and any(
        kw in query_lower for kw in ["chi tiết", "detail", "thông tin", "báo cáo"]
    ):
        effects.append(OpenStockDetailInstruction(payload={"symbol": symbol}))

    return effects


def _enhance_reply(
    reply_text: str,
    user_message: str,
    events_dump: List[Dict[str, Any]],
    agent_result: Dict[str, Any],
) -> str:
    """
    Cải thiện reply text để tự nhiên hơn, đa dạng hơn và có thông tin hơn.

    Logic:
    - Phân tích reply_text hiện tại
    - Trích xuất thông tin từ tool calls trong events_dump
    - Format lại để tự nhiên, không máy móc
    - Thêm context và insights hữu ích
    """
    import re
    import json
    from datetime import datetime

    if not reply_text or len(reply_text.strip()) < 10:
        return reply_text

    # Loại bỏ debug messages và technical info
    reply_cleaned = reply_text
    # Loại bỏ [DEBUG], [ERROR] tags
    reply_cleaned = re.sub(
        r"\[(DEBUG|ERROR|INFO|WARNING)\][^\n]*\n?",
        "",
        reply_cleaned,
        flags=re.IGNORECASE,
    )
    # Loại bỏ JSON dumps nếu có
    reply_cleaned = re.sub(r'\{[^{}]*"error"[^{}]*\}', "", reply_cleaned)

    # Nếu reply quá ngắn hoặc chỉ là technical info, giữ nguyên
    if len(reply_cleaned.strip()) < 20:
        return reply_text

    # Phân tích intent từ user message
    user_msg_lower = user_message.lower()
    reply_lower = reply_cleaned.lower()

    # Trích xuất số liệu từ reply (giá, phần trăm, số lượng)
    numbers = re.findall(r"\d+[.,]?\d*", reply_cleaned)
    symbols = re.findall(r"\b([A-Z]{3,4})\b", reply_cleaned)

    # Cải thiện format cho các trường hợp cụ thể

    # 1. Trả lời về giá cổ phiếu
    if any(kw in reply_lower for kw in ["giá", "price"]) and symbols:
        # Đảm bảo có format số đẹp
        reply_cleaned = re.sub(r"(\d+)(\d{3})(\d{3})", r"\1.\2.\3", reply_cleaned)
        # Thêm context nếu thiếu
        if "vnđ" not in reply_lower and "đồng" not in reply_lower:
            # Tìm số lớn (có thể là giá) và thêm VNĐ
            price_pattern = r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(?!%)"

            def add_vnd(match):
                num = match.group(1)
                # Nếu số > 1000, có thể là giá
                num_clean = num.replace(".", "").replace(",", "")
                if num_clean.isdigit() and int(num_clean) > 1000:
                    return f"{num} VNĐ"
                return num

            reply_cleaned = re.sub(price_pattern, add_vnd, reply_cleaned, count=1)

    # 2. Trả lời về gợi ý cổ phiếu
    if "gợi ý" in reply_lower or "tư vấn" in reply_lower or "suggest" in reply_lower:
        # Đảm bảo có format list đẹp
        if symbols and len(symbols) >= 2:
            # Tìm và format list symbols
            symbols_text = ", ".join(symbols[:3])
            if symbols_text not in reply_cleaned:
                # Thêm vào đầu reply nếu chưa có
                if not any(s in reply_cleaned for s in symbols):
                    reply_cleaned = f"Dựa trên phân tích profile và thị trường, tôi gợi ý {len(symbols)} mã cổ phiếu phù hợp: {symbols_text}. {reply_cleaned}"

    # 3. Trả lời về transaction/giao dịch
    if any(kw in reply_lower for kw in ["giao dịch", "transaction", "mua", "bán"]):
        # Đảm bảo có thông tin đầy đủ
        if "thành công" in reply_lower or "success" in reply_lower:
            if "đã" not in reply_lower and "vừa" not in reply_lower:
                reply_cleaned = f"Đã xử lý thành công! {reply_cleaned}"

    # 4. Trả lời về thống kê/lịch sử
    if any(kw in reply_lower for kw in ["thống kê", "stats", "lịch sử", "history"]):
        # Thêm format số đẹp cho phần trăm
        reply_cleaned = re.sub(
            r"(\d+\.?\d*)\s*%", lambda m: f"{float(m.group(1)):.1f}%", reply_cleaned
        )

        # Format số lớn với dấu phẩy
        def format_large_number(match):
            num_str = match.group(1).replace(".", "").replace(",", "")
            if num_str.isdigit():
                num = int(num_str)
                if num >= 1000:
                    return f"{num:,}".replace(",", ".")
            return match.group(0)

        reply_cleaned = re.sub(
            r"\b(\d{1,3}(?:[.,]\d{3})+)\b", format_large_number, reply_cleaned
        )

    # 5. Loại bỏ lặp lại và làm mượt câu
    # Loại bỏ khoảng trắng thừa
    reply_cleaned = re.sub(r"\s+", " ", reply_cleaned).strip()
    # Loại bỏ dấu chấm/câu lặp lại
    reply_cleaned = re.sub(r"\.{2,}", ".", reply_cleaned)
    # Đảm bảo có dấu chấm cuối câu
    if reply_cleaned and reply_cleaned[-1] not in ".!?":
        reply_cleaned += "."

    # 6. Thêm variety vào cách bắt đầu câu
    # Nếu reply bắt đầu bằng "Tôi" hoặc "Dựa trên" quá nhiều, thay đổi
    if reply_cleaned.startswith("Tôi"):
        alternatives = [
            "Dựa trên thông tin",
            "Theo phân tích",
            "Với dữ liệu hiện tại",
            "Căn cứ vào",
        ]
        # Giữ nguyên nếu đã đa dạng
        pass
    elif reply_cleaned.startswith("Dựa trên"):
        # Đã ổn
        pass

    # 7. Cải thiện tone - thân thiện hơn
    # Thay "bạn" bằng "bạn" (giữ nguyên) nhưng thêm emoji nếu phù hợp
    # Không thêm emoji vào reply chính, chỉ cải thiện text

    # 8. Đảm bảo có thông tin cụ thể
    # Nếu reply quá chung chung, thêm context từ user message
    if len(reply_cleaned) < 50 and symbols:
        # Thêm tên mã vào nếu thiếu
        for symbol in symbols[:2]:
            if symbol not in reply_cleaned:
                reply_cleaned = f"Về mã {symbol}, {reply_cleaned.lower()}"
                break

    # 9. Thêm variety vào cách diễn đạt
    # Thay đổi một số cụm từ phổ biến để đa dạng hơn
    replacements = {
        r"\bTôi sẽ\b": lambda m: ["Tôi sẽ", "Mình sẽ", "Tôi có thể"][
            hash(user_message) % 3
        ],
        r"\bDựa trên\b": lambda m: ["Dựa trên", "Theo", "Căn cứ vào", "Từ"][
            hash(user_message) % 4
        ],
        r"\bBạn có thể\b": lambda m: ["Bạn có thể", "Bạn nên", "Bạn có"][
            hash(user_message) % 3
        ],
    }

    # Chỉ thay đổi nếu không làm mất nghĩa
    for pattern, replacement in replacements.items():
        if re.search(pattern, reply_cleaned, re.IGNORECASE):
            # Chỉ thay 1 lần để giữ tự nhiên
            if isinstance(replacement, type(lambda: None)):
                new_text = replacement(None)
                reply_cleaned = re.sub(
                    pattern, new_text, reply_cleaned, count=1, flags=re.IGNORECASE
                )

    # 10. Cải thiện format số liệu
    # Format số lớn với dấu chấm phân cách hàng nghìn
    def format_number(match):
        num_str = match.group(1).replace(".", "").replace(",", "")
        if num_str.isdigit():
            num = int(num_str)
            if num >= 1000:
                # Format: 1.000.000
                formatted = f"{num:,}".replace(",", ".")
                return formatted
        return match.group(0)

    # Format số trong context giá cổ phiếu
    if any(kw in reply_lower for kw in ["giá", "price", "vnđ", "đồng"]):
        reply_cleaned = re.sub(r"\b(\d{4,})\b", format_number, reply_cleaned)

    # 11. Đảm bảo câu văn mượt mà
    # Loại bỏ từ lặp lại gần nhau
    words = reply_cleaned.split()
    cleaned_words = []
    prev_word = ""
    for word in words:
        if word.lower() != prev_word.lower() or len(word) > 3:  # Cho phép lặp từ ngắn
            cleaned_words.append(word)
        prev_word = word
    reply_cleaned = " ".join(cleaned_words)

    # 12. Thêm thông tin thời gian nếu phù hợp
    if any(kw in reply_lower for kw in ["hôm nay", "today", "hiện tại", "current"]):
        # Đảm bảo có context thời gian
        now = datetime.now()
        time_context = f"hôm nay ({now.strftime('%d/%m/%Y')})"
        if time_context not in reply_cleaned:
            # Không thêm nếu đã có thông tin thời gian
            pass

    return reply_cleaned.strip()


def _generate_suggestions(reply: str, query: str) -> list[SuggestionMessage]:
    """
    Generate suggestion messages dựa trên reply và query

    Logic:
    - Nếu reply về giá → suggest xem lịch sử
    - Nếu reply về 1 mã → suggest so sánh
    - Luôn suggest câu hỏi tương tự
    """
    import re

    suggestions = []
    reply_lower = reply.lower()
    query_lower = query.lower()

    # Gợi ý dữ liệu lịch sử nếu nói về giá hiện tại
    if any(
        kw in reply_lower for kw in ["giá hiện tại", "giá hôm nay", "current price"]
    ):
        suggestions.append(
            SuggestionMessage(
                text="Xem lịch sử giá 1 tháng qua",
                action="query:lịch sử giá",
                icon="📊",
            )
        )

    # Gợi ý so sánh nếu chỉ nhắc 1 cổ phiếu
    symbols = re.findall(r"\b([A-Z]{3,4})\b", query)
    if len(symbols) == 1:
        suggestions.append(
            SuggestionMessage(
                text=f"So sánh {symbols[0]} với mã khác",
                action=f"query:so sánh {symbols[0]}",
                icon="🔍",
            )
        )

    # Gợi ý thông tin tài chính nếu hỏi về giá
    if any(kw in query_lower for kw in ["giá", "price"]):
        suggestions.append(
            SuggestionMessage(
                text="Xem báo cáo tài chính",
                action="query:báo cáo tài chính",
                icon="📈",
            )
        )

    # Gợi ý mua nếu nói về giá
    if any(kw in reply_lower for kw in ["giá", "price"]) and "mua" not in query_lower:
        symbol = _extract_symbol_from_reply(query)
        if symbol:
            suggestions.append(
                SuggestionMessage(
                    text=f"Mua {symbol}",
                    action=f"buy:{symbol}",
                    icon="💰",
                )
            )

    # Luôn gợi ý trợ giúp
    if not suggestions:
        suggestions.append(
            SuggestionMessage(text="Tôi có thể hỏi gì khác?", action="help", icon="❓")
        )

    return suggestions[:3]  # Max 3 suggestions


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    agent=Depends(get_agent),
):
    """
    Nhận messages từ web, gọi ADK agent, trả text + ui_effects + suggestions.

    Flow:
    1. Extract user message
    2. Run agent
    3. Parse UI effects từ reply
    4. Generate suggestions
    5. Return ChatResponse
    """
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    # Lấy user message cuối cùng
    user_message = payload.messages[-1].content

    # Build conversation history cho agent
    # LlmAgent có thể nhận messages dưới dạng list hoặc string
    conversation_history = []
    for msg in payload.messages:
        if msg.role == "system":
            # System message có thể được set qua instruction của agent
            pass
        elif msg.role == "user":
            conversation_history.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            conversation_history.append({"role": "assistant", "content": msg.content})

    # Run agent
    agent_result = await _run_agent(
        agent, user_message, conversation_history, payload.meta
    )

    reply_text = agent_result.get("reply", "")
    events_dump = agent_result.get("events", [])

    # Cải thiện reply text để tự nhiên hơn, đa dạng hơn
    enhanced_reply = _enhance_reply(reply_text, user_message, events_dump, agent_result)

    # Import services để parse UI và generate suggestions
    from ...services import parse_ui_effects, extract_intent, generate_suggestions

    # Parse UI effects (dùng enhanced_reply để detect intent chính xác hơn)
    ui_effects = parse_ui_effects(enhanced_reply, user_message)

    # Extract intent và generate suggestions với full conversation history
    intent = extract_intent(enhanced_reply, user_message)
    # Truyền payload.messages (ChatMessage list) thay vì conversation_history (dict list)
    suggestions = generate_suggestions(
        enhanced_reply,
        user_message,
        intent,
        conversation_history=payload.messages,
        ui_effects=ui_effects,
    )

    return ChatResponse(
        reply=enhanced_reply,
        ui_effects=ui_effects,
        suggestion_messages=suggestions,
        raw_agent_output=agent_result,
    )


APP_NAME = "vnstock_app"
SESSION_SERVICE = InMemorySessionService()


async def _ensure_session(user_id: str, session_id: str):
    """
    Đảm bảo session tồn tại trong InMemorySessionService. Nếu chưa có thì tạo.
    """
    session = await SESSION_SERVICE.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if not session:
        session = await SESSION_SERVICE.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    return session


def _create_runner(agent) -> Runner:
    return Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=SESSION_SERVICE,
    )


def _run_blocking(agent, user_id: str, session_id: str, user_message: str):
    runner = _create_runner(agent)

    # Inject user_id vào user message để agent có thể sử dụng
    # Format: [USER_ID: user_id] ở đầu message
    enhanced_message = user_message
    if user_id and user_id != "user-unknown":
        # Chỉ inject nếu chưa có trong message
        if f"User ID của mình là {user_id}" not in user_message:
            enhanced_message = f"[USER_ID: {user_id}]\n{user_message}"

    content = types.Content(
        role="user",
        parts=[types.Part(text=enhanced_message)],
    )

    reply_text = ""
    events_dump = []
    text_parts = []  # Accumulate text từ nhiều events

    for event in runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        print(f"[DEBUG] Event received: type={type(event).__name__}")
        try:
            print(f"[DEBUG] Event content: {event}")
        except:
            pass
        # Parse event text từ nhiều cấu trúc khác nhau
        event_text = None
        event_author = getattr(event, "author", None)

        # Thử 1: event.content.parts[0].text (định dạng ADK chuẩn)
        if hasattr(event, "content") and event.content is not None:
            if hasattr(event.content, "parts") and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        event_text = part.text
                        break

        # Thử 2: event.text (simple format)
        if not event_text and hasattr(event, "text") and event.text:
            event_text = event.text

        # Thử 3: event.message (một số phiên bản ADK)
        if not event_text and hasattr(event, "message") and event.message:
            if isinstance(event.message, str):
                event_text = event.message
            elif hasattr(event.message, "text"):
                event_text = event.message.text

        # Thử 4: Kiểm tra xem event có phải là Content type không
        if not event_text:
            try:
                # Đôi khi event CHÍNH LÀ Content object
                if hasattr(event, "parts") and event.parts:
                    for part in event.parts:
                        if hasattr(part, "text") and part.text:
                            event_text = part.text
                            break
            except Exception:
                pass

        # Lưu thông tin event để debug
        try:
            event_info = {
                "author": event_author,
                "has_is_final": hasattr(event, "is_final_response"),
                "text": event_text,
                "type": type(event).__name__,
            }
            events_dump.append(event_info)
        except Exception:
            pass

        # Accumulate text từ model response
        # Ưu tiên lấy từ final response, nếu không có thì lấy từ tất cả model events
        
        # Check valid author (model OR agent name)
        is_valid_author = (
            event_author == "model" 
            or event_author == "vnstock_agent"
            or (hasattr(event, "content") and getattr(event.content, "role", "") == "model")
        )

        if event_text and is_valid_author:
            # Clean text if it is JSON
            cleaned_text = event_text
            should_use_text = True
            
            if event_text.strip().startswith("{"):
                try:
                    import json
                    # Try to parse
                    if "type" in event_text and "function" in event_text:
                        # This is likely a tool definition, IGNORE it to trigger fallback
                        should_use_text = False
                    elif "message" in event_text:
                        data = json.loads(event_text)
                        if "message" in data:
                            cleaned_text = data["message"]
                        else:
                             # JSON but no message, likely garbage
                             should_use_text = False
                    else:
                        # Unknown JSON, ignore to be safe and trigger fallback
                        should_use_text = False
                except:
                    # Not valid JSON, treat as text
                    pass
            
            if should_use_text:
                # Nếu là final response, ưu tiên dùng text này (có thể clear và chỉ dùng final)
                is_final = hasattr(event, "is_final_response") and getattr(
                    event, "is_final_response", False
                )
                if is_final:
                    # Final response - ưu tiên, nhưng vẫn append để giữ context
                    text_parts.append(cleaned_text)
                else:
                    # Intermediate response - append bình thường
                    text_parts.append(cleaned_text)

    # Join tất cả text parts thành một response hoàn chỉnh
    # Nếu có nhiều parts, join bằng space để tạo đoạn văn liền mạch
    reply_text = " ".join(text_parts).strip() if text_parts else ""

    # Nếu vẫn rỗng, thử lấy từ events_dump (fallback)
    if not reply_text and events_dump:
        # Tìm text từ events có author="model"
        for event_info in events_dump:
            if event_info.get("author") == "model" and event_info.get("text"):
                reply_text = event_info.get("text", "")
                break

    return reply_text, events_dump


async def _run_agent(
    agent, user_message: str, history: List[Dict[str, str]], meta=None
) -> Dict[str, Any]:
    user_id = getattr(meta, "user_id", "user-unknown") if meta else "user-unknown"
    raw_session_id = getattr(meta, "session_id", None) if meta else None
    session_id = raw_session_id or "default-session"

    # Set user_id vào backend_tools context để tools có thể sử dụng
    if user_id and user_id != "user-unknown":
        try:
            from agents.backend_tools import _set_current_user_id

            _set_current_user_id(user_id)
        except Exception as e:
            print(f"Warning: Failed to set user_id in backend_tools: {e}")

    try:
        await _ensure_session(user_id=user_id, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot create/get session: {e}")

    try:
        reply_text, events_dump = await asyncio.to_thread(
            _run_blocking,
            agent,
            user_id,
            session_id,
            user_message,
        )
    except Exception as e:
        # Log error nhưng không crash - trả về error message
        import traceback

        error_trace = traceback.format_exc()
        print(f"[ERROR] Agent runner failed: {e}")
        print(f"[ERROR] Traceback: {error_trace}")

        # Return friendly error message thay vì HTTP 500
        reply_text = f"Xin lỗi, đã có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại."
        events_dump = [
            {
                "error": str(e),
                "error_type": type(e).__name__,
            }
        ]

    # Nếu không có text, tạo fallback message dựa trên query
    if not reply_text:
        # Tạo reply mặc định dựa trên query để frontend vẫn có thể render UI effects
        if "mua" in user_message.lower() or "buy" in user_message.lower():
            reply_text = "Tôi sẽ hướng dẫn bạn mua cổ phiếu. Vui lòng chọn mã cổ phiếu và khối lượng bạn muốn mua."
        elif "tổng quan" in user_message.lower() or "market" in user_message.lower():
            reply_text = "Đây là tổng quan thị trường chứng khoán Việt Nam hôm nay."
        elif "tin tức" in user_message.lower() or "news" in user_message.lower():
            reply_text = "Đây là các tin tức mới nhất về thị trường chứng khoán."
        else:
            reply_text = (
                "Tôi đã nhận được yêu cầu của bạn. Vui lòng thử lại hoặc hỏi rõ hơn."
            )

    return {
        "reply": reply_text,
        "events": events_dump,
    }
