"""UI instruction schemas matching frontend FeatureInstruction types."""

from typing import List, Literal, Optional
from pydantic import BaseModel


class BuyFlowStep(BaseModel):
    id: str
    title: str
    description: Optional[str] = None


class MarketOverviewData(BaseModel):
    """Data for market overview panel."""

    indices: list[dict] = []
    mainChart: dict = {}
    trendingStocks: list[dict] = []


class NewsItem(BaseModel):
    id: str
    title: str
    source: str
    timeAgo: str
    sentiment: Literal["positive", "negative", "neutral"]


class NewsData(BaseModel):
    symbol: Optional[str] = None
    items: List[NewsItem]


class StockDetailData(BaseModel):
    symbol: str
    name: str
    description: Optional[str] = None
    price: float
    changePercent: float
    intradayChart: list[dict]


class BuyStockData(BaseModel):
    symbol: str
    currentPrice: float
    steps: List[BuyFlowStep]


class SellStockData(BaseModel):
    symbol: str
    currentPrice: float
    availableQuantity: float  # Số lượng cổ phiếu user đang có
    steps: List[BuyFlowStep]


class TransactionData(BaseModel):
    """Data for transaction confirmation"""

    transactionId: Optional[str] = None
    symbol: str
    type: Literal["buy", "sell"]
    quantity: float
    price: float
    totalAmount: float
    userId: str


class UserProfileData(BaseModel):
    """Data for user profile display"""

    userId: str
    fullName: Optional[str] = None
    email: Optional[str] = None
    balance: Optional[float] = None
    avatar: Optional[str] = None


class TransactionHistoryData(BaseModel):
    """Data for transaction history"""

    userId: str
    transactions: List[dict] = []


class TransactionStatsData(BaseModel):
    """Data for transaction statistics"""

    userId: str
    totalProfit: Optional[float] = None
    totalTransactions: Optional[int] = None
    winRate: Optional[float] = None


class RankingData(BaseModel):
    """Data for user ranking"""

    rankings: List[dict] = []
    userRank: Optional[int] = None


class ShowMarketOverviewInstruction(BaseModel):
    type: Literal["SHOW_MARKET_OVERVIEW"] = "SHOW_MARKET_OVERVIEW"


class OpenBuyStockInstruction(BaseModel):
    type: Literal["OPEN_BUY_STOCK"] = "OPEN_BUY_STOCK"
    payload: BuyStockData


class OpenSellStockInstruction(BaseModel):
    type: Literal["OPEN_SELL_STOCK"] = "OPEN_SELL_STOCK"
    payload: SellStockData


class ConfirmTransactionInstruction(BaseModel):
    type: Literal["CONFIRM_TRANSACTION"] = "CONFIRM_TRANSACTION"
    payload: TransactionData


class ShowUserProfileInstruction(BaseModel):
    type: Literal["SHOW_USER_PROFILE"] = "SHOW_USER_PROFILE"
    payload: UserProfileData


class ShowTransactionHistoryInstruction(BaseModel):
    type: Literal["SHOW_TRANSACTION_HISTORY"] = "SHOW_TRANSACTION_HISTORY"
    payload: TransactionHistoryData


class ShowTransactionStatsInstruction(BaseModel):
    type: Literal["SHOW_TRANSACTION_STATS"] = "SHOW_TRANSACTION_STATS"
    payload: TransactionStatsData


class ShowRankingInstruction(BaseModel):
    type: Literal["SHOW_RANKING"] = "SHOW_RANKING"
    payload: RankingData


class OpenNewsInstruction(BaseModel):
    type: Literal["OPEN_NEWS"] = "OPEN_NEWS"
    payload: NewsData


class OpenStockDetailInstruction(BaseModel):
    type: Literal["OPEN_STOCK_DETAIL"] = "OPEN_STOCK_DETAIL"
    payload: StockDetailData


# Union type cho tất cả feature instructions
FeatureInstruction = (
    ShowMarketOverviewInstruction
    | OpenBuyStockInstruction
    | OpenSellStockInstruction
    | OpenNewsInstruction
    | OpenStockDetailInstruction
    | ConfirmTransactionInstruction
    | ShowUserProfileInstruction
    | ShowTransactionHistoryInstruction
    | ShowTransactionStatsInstruction
    | ShowRankingInstruction
)
