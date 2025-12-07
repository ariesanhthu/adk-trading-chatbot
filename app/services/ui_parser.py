"""
Service để parse agent reply và generate UI effects
"""

import re
from typing import Optional

from ..schemas.ui import (
    ShowMarketOverviewInstruction,
    OpenBuyStockInstruction,
    OpenSellStockInstruction,
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


def extract_symbol_from_text(text: str) -> Optional[str]:
    """
    Extract stock symbol từ text (3-4 chữ cái in hoa)

    Args:
        text: Text chứa mã cổ phiếu

    Returns:
        Stock symbol hoặc None

    Example:
        >>> extract_symbol_from_text("Giá VCB hôm nay")
        "VCB"
    """
    matches = re.findall(r"\b([A-Z]{3,4})\b", text)
    return matches[0] if matches else None


def extract_user_id_from_text(text: str) -> Optional[str]:
    """
    Extract user ID từ text (có thể là MongoDB ObjectId hoặc custom ID)

    Args:
        text: Text chứa user ID

    Returns:
        User ID hoặc None
    """
    # Tìm MongoDB ObjectId format (24 hex chars)
    oid_match = re.search(r"\b([0-9a-fA-F]{24})\b", text)
    if oid_match:
        return oid_match.group(1)

    # Tìm user ID trong format "user-123" hoặc "userId: xxx"
    user_match = re.search(
        r"(?:user[_-]?id|user)[:=\s]+([a-zA-Z0-9_-]+)", text, re.IGNORECASE
    )
    if user_match:
        return user_match.group(1)

    return None


def parse_ui_effects(reply: str, query: str) -> list[FeatureInstruction]:
    """
    Parse agent reply để detect UI effects cần thiết

    Args:
        reply: Agent reply text
        query: User query text

    Returns:
        List of UI effect instructions

    Logic:
    - "tổng quan thị trường" → ShowMarketOverviewInstruction
    - "mua cổ phiếu" → OpenBuyStockInstruction
    - "chi tiết cổ phiếu" → OpenStockDetailInstruction
    """
    effects = []
    reply_lower = reply.lower()
    query_lower = query.lower()

    # 1. Market overview
    market_keywords = ["tổng quan", "market overview", "thị trường chung", "vnindex"]
    if any(kw in query_lower or kw in reply_lower for kw in market_keywords):
        effects.append(ShowMarketOverviewInstruction())

    # 2. Buy stock
    buy_keywords = ["mua", "buy", "đặt lệnh mua", "order buy"]
    if any(kw in query_lower for kw in buy_keywords):
        symbol = extract_symbol_from_text(reply) or extract_symbol_from_text(query)
        if symbol:
            effects.append(
                OpenBuyStockInstruction(
                    payload=BuyStockData(
                        symbol=symbol,
                        currentPrice=0.0,  # Agent should provide this
                        steps=[
                            BuyFlowStep(id="choose_volume", title="Chọn khối lượng"),
                            BuyFlowStep(id="choose_price", title="Chọn giá đặt lệnh"),
                            BuyFlowStep(id="confirm", title="Xác nhận lệnh"),
                        ],
                    )
                )
            )

    # 3. Sell stock
    sell_keywords = ["bán", "sell", "đặt lệnh bán", "order sell"]
    if any(kw in query_lower for kw in sell_keywords):
        symbol = extract_symbol_from_text(reply) or extract_symbol_from_text(query)
        if symbol:
            effects.append(
                OpenSellStockInstruction(
                    payload=SellStockData(
                        symbol=symbol,
                        currentPrice=0.0,  # Agent should provide this
                        availableQuantity=0.0,  # Will be fetched from backend
                        steps=[
                            BuyFlowStep(id="choose_volume", title="Chọn khối lượng"),
                            BuyFlowStep(id="choose_price", title="Chọn giá đặt lệnh"),
                            BuyFlowStep(id="confirm", title="Xác nhận lệnh"),
                        ],
                    )
                )
            )

    # 4. User profile
    profile_keywords = [
        "thông tin tài khoản",
        "profile",
        "tài khoản",
        "số dư",
        "balance",
    ]
    if any(kw in query_lower for kw in profile_keywords):
        # Extract userId from query or use default
        userId = extract_user_id_from_text(query) or "current_user"
        effects.append(
            ShowUserProfileInstruction(payload=UserProfileData(userId=userId))
        )

    # 5. Transaction history
    history_keywords = [
        "lịch sử giao dịch",
        "transaction history",
        "giao dịch",
        "lệnh đã đặt",
    ]
    if any(kw in query_lower for kw in history_keywords):
        userId = extract_user_id_from_text(query) or "current_user"
        effects.append(
            ShowTransactionHistoryInstruction(
                payload=TransactionHistoryData(userId=userId)
            )
        )

    # 6. Transaction stats
    stats_keywords = [
        "thống kê",
        "statistics",
        "lợi nhuận",
        "profit",
        "tỷ lệ thắng",
        "win rate",
    ]
    if any(kw in query_lower for kw in stats_keywords):
        userId = extract_user_id_from_text(query) or "current_user"
        effects.append(
            ShowTransactionStatsInstruction(payload=TransactionStatsData(userId=userId))
        )

    # 7. Ranking
    ranking_keywords = ["bảng xếp hạng", "ranking", "top", "xếp hạng"]
    if any(kw in query_lower for kw in ranking_keywords):
        effects.append(ShowRankingInstruction(payload=RankingData()))

    # 8. Stock detail
    detail_keywords = ["chi tiết", "detail", "thông tin", "báo cáo", "phân tích"]
    symbol = extract_symbol_from_text(query)
    if symbol and any(kw in query_lower for kw in detail_keywords):
        effects.append(OpenStockDetailInstruction(payload={"symbol": symbol}))

    return effects


def extract_intent(reply: str, query: str) -> Optional[str]:
    """
    Extract user intent từ query/reply

    Returns:
        Intent string: "market_overview", "buy_stock", "sell_stock", "stock_detail",
        "price_query", "user_profile", "transaction_history", "transaction_stats",
        "ranking", "view_news", None
    """
    query_lower = query.lower()
    reply_lower = reply.lower()

    # Market overview
    if any(kw in query_lower for kw in ["tổng quan", "market overview", "vnindex"]):
        return "market_overview"

    # Buy stock
    if any(kw in query_lower for kw in ["mua", "buy", "đặt lệnh mua"]):
        return "buy_stock"

    # Sell stock
    if any(kw in query_lower for kw in ["bán", "sell", "đặt lệnh bán"]):
        return "sell_stock"

    # User profile
    if any(
        kw in query_lower
        for kw in ["thông tin tài khoản", "profile", "tài khoản", "số dư"]
    ):
        return "user_profile"

    # Transaction history
    if any(
        kw in query_lower
        for kw in ["lịch sử giao dịch", "transaction history", "giao dịch"]
    ):
        return "transaction_history"

    # Transaction stats
    if any(
        kw in query_lower for kw in ["thống kê", "statistics", "lợi nhuận", "profit"]
    ):
        return "transaction_stats"

    # Ranking
    if any(kw in query_lower for kw in ["bảng xếp hạng", "ranking", "top"]):
        return "ranking"

    # Stock detail
    if any(kw in query_lower for kw in ["chi tiết", "detail", "thông tin chi tiết"]):
        return "stock_detail"

    # View news
    if any(kw in query_lower for kw in ["tin tức", "news", "sự kiện"]):
        return "view_news"

    # Price query
    if any(kw in query_lower for kw in ["giá", "price"]):
        return "price_query"

    return None
