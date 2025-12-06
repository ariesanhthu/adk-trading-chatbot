"""Chat endpoint for chatbot API."""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..deps import get_agent
from ...schemas.chat import ChatRequest, ChatResponse
from ...schemas.ui import (
    ShowMarketOverviewInstruction,
    OpenBuyStockInstruction,
    OpenNewsInstruction,
    OpenStockDetailInstruction,
    FeatureInstruction,
    BuyStockData,
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

    return ui_effects


def _extract_symbol_from_reply(reply: str) -> Optional[str]:
    """Extract stock symbol from reply text."""
    import re

    # Tìm mã chứng khoán (thường là 3-4 chữ cái in hoa)
    matches = re.findall(r"\b([A-Z]{3,4})\b", reply)
    if matches:
        return matches[0]
    return None


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    agent=Depends(get_agent),
):
    """
    Nhận messages từ web, gọi ADK agent, trả text + ui_effects.
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

    agent_result = await _run_agent(
        agent, user_message, conversation_history, payload.meta
    )

    reply_text = agent_result.get("reply", "")

    return ChatResponse(
        reply=reply_text,
        ui_effects=[],
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

    content = types.Content(
        role="user",
        parts=[types.Part(text=user_message)],
    )

    reply_text = ""
    events_dump = []

    for event in runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        print("=== RAW EVENT ===")
        print("TYPE:", type(event))
        print("DIR:", [a for a in dir(event) if not a.startswith("_")])
        try:
            print("REPR:", repr(event))
        except Exception:
            pass

        event_text = None
        if getattr(event, "content", None) is not None:
            parts = getattr(event.content, "parts", None)
            if parts and len(parts) > 0 and getattr(parts[0], "text", None) is not None:
                event_text = parts[0].text

        try:
            event_info = {
                "author": getattr(event, "author", None),
                "has_is_final": hasattr(event, "is_final_response"),
                "text": event_text,
            }
            events_dump.append(event_info)
        except Exception:
            pass

        if event_text:
            reply_text = event_text

    return reply_text, events_dump


async def _run_agent(
    agent, user_message: str, history: List[Dict[str, str]], meta=None
) -> Dict[str, Any]:
    user_id = getattr(meta, "user_id", "user-unknown") if meta else "user-unknown"
    raw_session_id = getattr(meta, "session_id", None) if meta else None
    session_id = raw_session_id or "default-session"

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
        raise HTTPException(status_code=500, detail=f"Agent runner error: {e}")

    if not reply_text:
        reply_text = "[DEBUG] Agent không trả về text – kiểm tra raw_agent_output.events để debug."

    return {
        "reply": reply_text,
        "events": events_dump,
    }
