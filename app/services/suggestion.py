"""
Service để generate suggestion messages cho user
"""

import re
from typing import List, Optional

from ..schemas.chat import ChatMessage, SuggestionMessage


def generate_suggestions(
    reply: str,
    query: str,
    intent: Optional[str] = None,
    conversation_history: Optional[List[ChatMessage]] = None,
    ui_effects: Optional[List] = None,
) -> list[SuggestionMessage]:
    """
    Generate suggestion messages dựa trên reply, query, intent và conversation history.
    Suggestions được tạo bằng cách kết hợp thông tin từ cả reply, query và context của conversation.

    Args:
        reply: Agent reply text
        query: User query text (message cuối cùng)
        intent: Intent đã detect (optional)
        conversation_history: Toàn bộ conversation history (optional)
        ui_effects: UI effects từ reply hiện tại (optional)

    Returns:
        List of suggestion messages (max 3, luôn có ít nhất 1)

    Example:
        >>> suggestions = generate_suggestions("Giá VCB hôm nay là 95,000 VNĐ", "Giá VCB?")
        >>> print(suggestions[0].text)
        "Xem lịch sử giá VCB 1 tháng qua"
    """
    suggestions = []
    reply_lower = reply.lower() if reply else ""
    query_lower = query.lower() if query else ""

    # Bỏ qua debug messages khi generate suggestions
    if "[DEBUG]" in reply or not reply or len(reply.strip()) < 10:
        # Nếu reply không hợp lệ, dùng query để generate suggestions
        reply_lower = query_lower

    # Phân tích conversation history để detect flow state
    flow_state = _detect_flow_state(conversation_history, reply, ui_effects)

    # Extract symbols từ CẢ reply VÀ query (kết hợp để có đầy đủ context)
    symbols_from_query = re.findall(r"\b([A-Z]{3,4})\b", query)
    symbols_from_reply = re.findall(r"\b([A-Z]{3,4})\b", reply)
    # Kết hợp và loại bỏ trùng lặp, ưu tiên symbols từ query
    all_symbols = list(dict.fromkeys(symbols_from_query + symbols_from_reply))
    primary_symbol = all_symbols[0] if all_symbols else None

    # Extract context từ reply
    reply_has_price = any(kw in reply_lower for kw in ["giá", "price", "vnđ", "đồng"])
    reply_has_current_price = any(
        kw in reply_lower
        for kw in ["giá hiện tại", "giá hôm nay", "current price", "giá đóng cửa"]
    )
    reply_has_history = any(
        kw in reply_lower for kw in ["lịch sử", "history", "quá khứ", "trước đây"]
    )
    reply_has_news = any(kw in reply_lower for kw in ["tin tức", "news", "sự kiện"])
    reply_has_market_overview = any(
        kw in reply_lower
        for kw in ["tổng quan", "market overview", "thị trường", "vn-index"]
    )
    reply_has_transaction = any(
        kw in reply_lower for kw in ["giao dịch", "transaction", "mua", "bán"]
    )

    # Extract context từ query
    query_has_price = any(kw in query_lower for kw in ["giá", "price"])
    query_has_buy_sell = any(kw in query_lower for kw in ["mua", "bán", "buy", "sell"])

    # 1. Gợi ý lịch sử giá nếu reply có giá hiện tại
    # Kết hợp: reply có giá hiện tại + query có symbol → suggest lịch sử với symbol cụ thể
    if reply_has_current_price:
        if primary_symbol:
            suggestions.append(
                SuggestionMessage(
                    text=f"Xem lịch sử giá {primary_symbol} 1 tháng qua",
                    action=f"query:lịch sử giá {primary_symbol}",
                    icon="📊",
                )
            )
        else:
            suggestions.append(
                SuggestionMessage(
                    text="Xem lịch sử giá 1 tháng qua",
                    action="query:lịch sử giá",
                    icon="📊",
                )
            )

    # 2. Gợi ý so sánh nếu query/reply chỉ nhắc 1 cổ phiếu
    # Kết hợp: query có 1 symbol + intent là price_query → suggest so sánh
    if len(all_symbols) == 1 and (intent == "price_query" or query_has_price):
        suggestions.append(
            SuggestionMessage(
                text=f"So sánh {primary_symbol} với mã khác",
                action=f"query:so sánh {primary_symbol}",
                icon="🔍",
            )
        )

    # 3. Gợi ý báo cáo tài chính nếu hỏi về giá và có symbol
    # Kết hợp: query về giá + có symbol → suggest báo cáo tài chính
    if (intent == "price_query" or query_has_price) and primary_symbol:
        suggestions.append(
            SuggestionMessage(
                text=f"Xem báo cáo tài chính {primary_symbol}",
                action=f"query:báo cáo tài chính {primary_symbol}",
                icon="📈",
            )
        )

    # 4. Gợi ý mua/bán nếu reply có giá và query chưa có mua/bán
    # Kết hợp: reply có giá + query có symbol + chưa có mua/bán → suggest mua/bán
    if reply_has_price and primary_symbol and not query_has_buy_sell:
        if intent not in ["buy_stock", "sell_stock"]:
            suggestions.append(
                SuggestionMessage(
                    text=f"Mua {primary_symbol}",
                    action=f"buy:{primary_symbol}",
                    icon="💰",
                )
            )
            # Chỉ suggest bán nếu đã có trong portfolio (có thể check sau)
            suggestions.append(
                SuggestionMessage(
                    text=f"Bán {primary_symbol}",
                    action=f"sell:{primary_symbol}",
                    icon="💸",
                )
            )

    # 5. Gợi ý tin tức nếu reply có tin tức hoặc query về tin tức
    # Kết hợp: reply có tin tức + có symbol → suggest xem thêm tin tức
    if (reply_has_news or intent == "view_news") and primary_symbol:
        suggestions.append(
            SuggestionMessage(
                text=f"Xem tin tức {primary_symbol}",
                action=f"query:tin tức {primary_symbol}",
                icon="📰",
            )
        )

    # 6. Gợi ý chi tiết cổ phiếu nếu query về giá/chi tiết và có symbol
    # Kết hợp: query về giá/chi tiết + có symbol + chưa phải stock_detail → suggest chi tiết
    if (
        (query_has_price or intent == "price_query")
        and primary_symbol
        and intent != "stock_detail"
    ):
        suggestions.append(
            SuggestionMessage(
                text=f"Xem chi tiết {primary_symbol}",
                action=f"query:chi tiết {primary_symbol}",
                icon="📋",
            )
        )

    # 7. Gợi ý tổng quan thị trường nếu đang xem 1 cổ phiếu
    # Kết hợp: query có symbol + không phải market_overview → suggest tổng quan
    if primary_symbol and intent != "market_overview":
        suggestions.append(
            SuggestionMessage(
                text="Xem tổng quan thị trường",
                action="query:tổng quan thị trường",
                icon="🌐",
            )
        )

    # 8. Gợi ý xem tài khoản nếu chưa hỏi về tài khoản
    if intent not in ["user_profile", "transaction_history", "transaction_stats"]:
        suggestions.append(
            SuggestionMessage(
                text="Xem thông tin tài khoản",
                action="query:thông tin tài khoản",
                icon="👤",
            )
        )

    # 9. Gợi ý xem lịch sử giao dịch nếu chưa hỏi
    if intent != "transaction_history" and not reply_has_transaction:
        suggestions.append(
            SuggestionMessage(
                text="Xem lịch sử giao dịch",
                action="query:lịch sử giao dịch",
                icon="📋",
            )
        )

    # 10. Gợi ý xem bảng xếp hạng nếu chưa hỏi
    if intent != "ranking":
        suggestions.append(
            SuggestionMessage(
                text="Xem bảng xếp hạng",
                action="query:bảng xếp hạng",
                icon="🏆",
            )
        )

    # 11. Gợi ý giá cổ phiếu khác nếu đang xem tổng quan thị trường
    if intent == "market_overview" or reply_has_market_overview:
        # Nếu có symbol trong reply, suggest giá của symbol đó
        if primary_symbol:
            suggestions.append(
                SuggestionMessage(
                    text=f"Giá cổ phiếu {primary_symbol} hôm nay?",
                    action=f"query:Giá {primary_symbol} hôm nay",
                    icon="💹",
                )
            )
        else:
            suggestions.append(
                SuggestionMessage(
                    text="Giá cổ phiếu VCB hôm nay?",
                    action="query:Giá VCB hôm nay",
                    icon="💹",
                )
            )

    # 12. Gợi ý dựa trên flow state (ưu tiên cao nhất)
    if flow_state:
        flow_suggestions = _generate_flow_suggestions(flow_state, primary_symbol, reply_lower)
        # Thêm flow suggestions vào đầu (ưu tiên)
        suggestions = flow_suggestions + suggestions

    # Loại bỏ trùng lặp (giữ lại suggestion đầu tiên)
    seen_texts = set()
    unique_suggestions = []
    for sug in suggestions:
        if sug.text not in seen_texts:
            seen_texts.add(sug.text)
            unique_suggestions.append(sug)

    # Đảm bảo có ít nhất 1 gợi ý
    if not unique_suggestions:
        unique_suggestions = get_default_suggestions()[:1]
    elif len(unique_suggestions) < 3:
        # Thêm gợi ý mặc định nếu chưa đủ 3
        default_suggestions = get_default_suggestions()
        for default in default_suggestions:
            if len(unique_suggestions) >= 3:
                break
            if default.text not in seen_texts:
                unique_suggestions.append(default)

    # Return max 3 suggestions (luôn có ít nhất 1)
    return unique_suggestions[:3]


def _detect_flow_state(
    conversation_history: Optional[List[ChatMessage]],
    current_reply: str,
    current_ui_effects: Optional[List],
) -> Optional[dict]:
    """
    Detect flow state từ conversation history và UI effects.
    
    Returns:
        Dict với keys: 'type' (buy/sell/confirm), 'symbol', 'step' (fill/confirm)
        None nếu không có flow đang diễn ra
    """
    if not conversation_history:
        return None

    # Kiểm tra UI effects hiện tại
    if current_ui_effects:
        for effect in current_ui_effects:
            effect_type = getattr(effect, "type", None) or (
                effect.get("type") if isinstance(effect, dict) else None
            )
            if effect_type == "OPEN_BUY_STOCK":
                payload = getattr(effect, "payload", None) or (
                    effect.get("payload") if isinstance(effect, dict) else None
                )
                symbol = None
                if payload:
                    symbol = (
                        getattr(payload, "symbol", None)
                        or (payload.get("symbol") if isinstance(payload, dict) else None)
                    )
                return {"type": "buy", "symbol": symbol, "step": "fill"}
            elif effect_type == "OPEN_SELL_STOCK":
                payload = getattr(effect, "payload", None) or (
                    effect.get("payload") if isinstance(effect, dict) else None
                )
                symbol = None
                if payload:
                    symbol = (
                        getattr(payload, "symbol", None)
                        or (payload.get("symbol") if isinstance(payload, dict) else None)
                    )
                return {"type": "sell", "symbol": symbol, "step": "fill"}
            elif effect_type == "CONFIRM_TRANSACTION":
                payload = getattr(effect, "payload", None) or (
                    effect.get("payload") if isinstance(effect, dict) else None
                )
                symbol = None
                if payload:
                    symbol = (
                        getattr(payload, "symbol", None)
                        or (payload.get("symbol") if isinstance(payload, dict) else None)
                    )
                return {"type": "confirm", "symbol": symbol, "step": "confirm"}

    # Phân tích conversation history để tìm flow state
    # Tìm các message trước đó về mua/bán
    buy_sell_symbol = None
    flow_type = None

    # Duyệt ngược từ message cuối về đầu
    for msg in reversed(conversation_history):
        content = msg.content.lower() if msg.content else ""
        
        # Tìm intent mua/bán trong conversation
        if "mua" in content or "buy" in content:
            flow_type = "buy"
            # Extract symbol
            symbols = re.findall(r"\b([A-Z]{3,4})\b", msg.content)
            if symbols:
                buy_sell_symbol = symbols[0]
            break
        elif "bán" in content or "sell" in content:
            flow_type = "sell"
            # Extract symbol
            symbols = re.findall(r"\b([A-Z]{3,4})\b", msg.content)
            if symbols:
                buy_sell_symbol = symbols[0]
            break

    # Kiểm tra reply hiện tại có gợi ý về form fill không
    current_reply_lower = current_reply.lower() if current_reply else ""
    if flow_type and (
        "hướng dẫn" in current_reply_lower
        or "điền" in current_reply_lower
        or "chọn" in current_reply_lower
        or "khối lượng" in current_reply_lower
        or "giá đặt lệnh" in current_reply_lower
    ):
        return {"type": flow_type, "symbol": buy_sell_symbol, "step": "fill"}

    # Kiểm tra có xác nhận giao dịch không
    if any(
        kw in current_reply_lower
        for kw in ["đã xác nhận", "giao dịch thành công", "transaction", "lệnh đã được"]
    ):
        return {"type": "confirm", "symbol": buy_sell_symbol, "step": "confirm"}

    return None


def _generate_flow_suggestions(
    flow_state: dict, symbol: Optional[str], reply_lower: str
) -> list[SuggestionMessage]:
    """
    Generate suggestions dựa trên flow state.
    
    Args:
        flow_state: Dict với keys: 'type', 'symbol', 'step'
        symbol: Symbol từ query/reply hiện tại
        reply_lower: Reply text lowercase
    
    Returns:
        List of suggestions cho flow hiện tại
    """
    suggestions = []
    flow_type = flow_state.get("type")
    flow_symbol = flow_state.get("symbol") or symbol
    step = flow_state.get("step")

    if flow_type == "buy" and step == "fill":
        # Đang ở bước fill form mua
        if flow_symbol:
            suggestions.append(
                SuggestionMessage(
                    text=f"Xác nhận mua {flow_symbol}",
                    action=f"confirm:buy:{flow_symbol}",
                    icon="✅",
                )
            )
            suggestions.append(
                SuggestionMessage(
                    text=f"Hủy mua {flow_symbol}",
                    action=f"cancel:buy:{flow_symbol}",
                    icon="❌",
                )
            )
        else:
            suggestions.append(
                SuggestionMessage(
                    text="Xác nhận mua",
                    action="confirm:buy",
                    icon="✅",
                )
            )

    elif flow_type == "sell" and step == "fill":
        # Đang ở bước fill form bán
        if flow_symbol:
            suggestions.append(
                SuggestionMessage(
                    text=f"Xác nhận bán {flow_symbol}",
                    action=f"confirm:sell:{flow_symbol}",
                    icon="✅",
                )
            )
            suggestions.append(
                SuggestionMessage(
                    text=f"Hủy bán {flow_symbol}",
                    action=f"cancel:sell:{flow_symbol}",
                    icon="❌",
                )
            )
        else:
            suggestions.append(
                SuggestionMessage(
                    text="Xác nhận bán",
                    action="confirm:sell",
                    icon="✅",
                )
            )

    elif flow_type == "confirm" and step == "confirm":
        # Đã xác nhận giao dịch
        suggestions.append(
            SuggestionMessage(
                text="Xem lịch sử giao dịch",
                action="query:lịch sử giao dịch",
                icon="📋",
            )
        )
        suggestions.append(
            SuggestionMessage(
                text="Xem thông tin tài khoản",
                action="query:thông tin tài khoản",
                icon="👤",
            )
        )
        if flow_symbol:
            suggestions.append(
                SuggestionMessage(
                    text=f"Xem chi tiết {flow_symbol}",
                    action=f"query:chi tiết {flow_symbol}",
                    icon="📊",
                )
            )

    return suggestions


def get_default_suggestions() -> list[SuggestionMessage]:
    """
    Get default suggestion messages khi không có context

    Returns:
        List of 3 default suggestions
    """
    return [
        SuggestionMessage(
            text="Xem tổng quan thị trường",
            action="query:tổng quan thị trường",
            icon="🌐",
        ),
        SuggestionMessage(
            text="Giá cổ phiếu VCB hôm nay?",
            action="query:Giá VCB hôm nay",
            icon="💹",
        ),
        SuggestionMessage(
            text="Tìm hiểu thêm",
            action="help",
            icon="❓",
        ),
    ]
