"""
Service để generate suggestion messages cho user
"""

import re
from typing import Optional

from ..schemas.chat import SuggestionMessage


def generate_suggestions(
    reply: str, query: str, intent: Optional[str] = None
) -> list[SuggestionMessage]:
    """
    Generate suggestion messages dựa trên reply, query và intent

    Args:
        reply: Agent reply text
        query: User query text
        intent: Intent đã detect (optional)

    Returns:
        List of suggestion messages (max 3, luôn có ít nhất 1)

    Example:
        >>> suggestions = generate_suggestions("Giá VCB hôm nay là 95,000 VNĐ", "Giá VCB?")
        >>> print(suggestions[0].text)
        "Xem lịch sử giá 1 tháng qua"
    """
    suggestions = []
    reply_lower = reply.lower() if reply else ""
    query_lower = query.lower() if query else ""

    # Bỏ qua debug messages khi generate suggestions
    if "[DEBUG]" in reply or not reply or len(reply.strip()) < 10:
        # Nếu reply không hợp lệ, dùng query để generate suggestions
        reply_lower = query_lower

    # 1. Gợi ý dữ liệu lịch sử nếu nói về giá hiện tại
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

    # 2. Gợi ý so sánh nếu chỉ nhắc 1 cổ phiếu
    symbols = re.findall(r"\b([A-Z]{3,4})\b", query)
    if len(symbols) == 1 and intent == "price_query":
        suggestions.append(
            SuggestionMessage(
                text=f"So sánh {symbols[0]} với mã khác",
                action=f"query:so sánh {symbols[0]}",
                icon="🔍",
            )
        )

    # 3. Gợi ý báo cáo tài chính nếu hỏi về giá
    if intent == "price_query" and symbols:
        suggestions.append(
            SuggestionMessage(
                text="Xem báo cáo tài chính",
                action="query:báo cáo tài chính",
                icon="📈",
            )
        )

    # 4. Gợi ý mua/bán nếu nói về giá
    if any(kw in reply_lower for kw in ["giá", "price"]):
        if symbols and len(symbols) == 1:
            if "mua" not in query_lower and "bán" not in query_lower:
                suggestions.append(
                    SuggestionMessage(
                        text=f"Mua {symbols[0]}",
                        action=f"buy:{symbols[0]}",
                        icon="💰",
                    )
                )
                suggestions.append(
                    SuggestionMessage(
                        text=f"Bán {symbols[0]}",
                        action=f"sell:{symbols[0]}",
                        icon="💸",
                    )
                )

    # 5. Gợi ý tổng quan thị trường nếu hỏi về 1 cổ phiếu
    if symbols and len(symbols) == 1 and intent != "market_overview":
        suggestions.append(
            SuggestionMessage(
                text="Xem tổng quan thị trường",
                action="query:tổng quan thị trường",
                icon="🌐",
            )
        )

    # 6. Gợi ý xem tài khoản nếu chưa hỏi
    if intent not in ["user_profile", "transaction_history", "transaction_stats"]:
        suggestions.append(
            SuggestionMessage(
                text="Xem thông tin tài khoản",
                action="query:thông tin tài khoản",
                icon="👤",
            )
        )

    # 7. Gợi ý xem lịch sử giao dịch
    if intent != "transaction_history":
        suggestions.append(
            SuggestionMessage(
                text="Xem lịch sử giao dịch",
                action="query:lịch sử giao dịch",
                icon="📋",
            )
        )

    # 8. Gợi ý xem bảng xếp hạng
    if intent != "ranking":
        suggestions.append(
            SuggestionMessage(
                text="Xem bảng xếp hạng",
                action="query:bảng xếp hạng",
                icon="🏆",
            )
        )

    # 6. Gợi ý tin tức nếu hỏi về chi tiết cổ phiếu
    if intent == "stock_detail" and symbols:
        suggestions.append(
            SuggestionMessage(
                text=f"Xem tin tức {symbols[0]}",
                action=f"query:tin tức {symbols[0]}",
                icon="📰",
            )
        )

    # 7. Gợi ý mua cổ phiếu nếu đang xem tổng quan thị trường
    if intent == "market_overview":
        suggestions.append(
            SuggestionMessage(
                text="Xem giá cổ phiếu VCB",
                action="query:Giá VCB hôm nay",
                icon="💹",
            )
        )

    # 8. Gợi ý trợ giúp mặc định nếu không có gợi ý cụ thể
    if not suggestions:
        # Luôn có ít nhất 1 gợi ý mặc định
        suggestions = get_default_suggestions()[:3]
    else:
        # Đảm bảo có ít nhất 1 gợi ý, nếu chưa đủ 3 thì thêm gợi ý mặc định
        if len(suggestions) < 3:
            default_suggestions = get_default_suggestions()
            for default in default_suggestions:
                if len(suggestions) >= 3:
                    break
                # Chỉ thêm nếu chưa có suggestion tương tự
                if not any(s.text == default.text for s in suggestions):
                    suggestions.append(default)

    # Return max 3 suggestions (luôn có ít nhất 1)
    return suggestions[:3] if suggestions else get_default_suggestions()[:1]


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
