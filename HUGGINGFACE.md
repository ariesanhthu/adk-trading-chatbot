# Hướng dẫn sử dụng VNStock MCP Server trên HuggingFace Spaces

## Thông tin Deployment

- **URL**: https://huggingface.co/spaces/Arischi05/mcp-vnstock
- **Transport**: SSE (Server-Sent Events)
- **Port**: 7860
- **Mount Path**: `/`

## Kiểm tra trạng thái và Logs

### Xem logs real-time

```bash
# Set HuggingFace token (lấy tại https://huggingface.co/settings/tokens)
export HF_TOKEN="your_token_here"

# Xem logs của server
curl -N \
     -H "Authorization: Bearer $HF_TOKEN" \
     "https://huggingface.co/api/spaces/Arischi05/mcp-vnstock/logs/run"
```

### Xem build logs

```bash
curl -N \
     -H "Authorization: Bearer $HF_TOKEN" \
     "https://huggingface.co/api/spaces/Arischi05/mcp-vnstock/logs/build"
```

## Kết nối với MCP Server

### 1. Sử dụng Python với MCP Client

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    # Kết nối với HuggingFace Space qua SSE
    async with sse_client(
        "https://huggingface.co/spaces/Arischi05/mcp-vnstock/sse"
    ) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")
            
            # Call tool: Lấy thông tin công ty VCB
            result = await session.call_tool(
                "get_company_overview",
                arguments={"symbol": "VCB", "output_format": "json"}
            )
            print(result.content)

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Sử dụng curl để test SSE

```bash
# Test SSE endpoint (streaming)
curl -N "https://huggingface.co/spaces/Arischi05/mcp-vnstock/sse"
```

### 3. Sử dụng JavaScript/TypeScript

```javascript
const eventSource = new EventSource(
  'https://huggingface.co/spaces/Arischi05/mcp-vnstock/sse'
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
  eventSource.close();
};
```

### 4. Gọi tool qua HTTP POST (nếu hỗ trợ)

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "get_company_overview",
         "arguments": {
           "symbol": "VCB",
           "output_format": "json"
         }
       }
     }' \
     "https://huggingface.co/spaces/Arischi05/mcp-vnstock/"
```

## Restart Server

### Qua HuggingFace UI

1. Vào https://huggingface.co/spaces/Arischi05/mcp-vnstock
2. Click vào menu "..." hoặc "Settings"
3. Chọn "Restart this Space"

### Qua API

```bash
curl -X POST \
     -H "Authorization: Bearer $HF_TOKEN" \
     "https://huggingface.co/api/spaces/Arischi05/mcp-vnstock/restart"
```

## Các Tools có sẵn

Server cung cấp các tools sau:

### Company Tools
- `get_company_overview(symbol, output_format)`
- `get_company_news(symbol, page_size, page, output_format)`
- `get_company_events(symbol, page_size, page, output_format)`
- `get_company_shareholders(symbol, output_format)`

### Finance Tools
- `get_income_statement(symbol, period, output_format)`
- `get_balance_sheet(symbol, period, output_format)`
- `get_cash_flow(symbol, period, output_format)`

### Quote Tools
- `get_quote(symbol, output_format)`
- `get_price_history(symbol, start_date, end_date, interval, output_format)`
- `get_price_board(symbols, output_format)`

### Trading Tools
- `get_trading_data(symbol, start_date, end_date, output_format)`
- `get_order_book(symbol, output_format)`

### Fund Tools
- `get_fund_list(output_format)`
- `get_fund_nav(symbol, output_format)`

### Misc Tools
- `get_gold_price(date, source, output_format)`
- `get_exchange_rate(date, output_format)`

Xem chi tiết trong [README_vn.md](README_vn.md).

## Ví dụ sử dụng

### Lấy thông tin công ty

```python
result = await session.call_tool(
    "get_company_overview",
    arguments={"symbol": "VCB", "output_format": "json"}
)
```

### Lấy giá cổ phiếu

```python
result = await session.call_tool(
    "get_quote",
    arguments={"symbol": "VCB", "output_format": "json"}
)
```

### Lấy giá vàng

```python
result = await session.call_tool(
    "get_gold_price",
    arguments={"source": "SJC", "output_format": "json"}
)
```

## Troubleshooting

### Server không phản hồi

1. Kiểm tra status của Space: https://huggingface.co/spaces/Arischi05/mcp-vnstock
2. Xem logs để tìm lỗi
3. Restart Space nếu cần

### Connection refused

- Space có thể đang "Sleeping" (không được sử dụng một thời gian)
- Restart Space để wake up

### 401 Unauthorized

- Đảm bảo đã set `HF_TOKEN` đúng
- Token phải có quyền truy cập Space

### Cold Start

- Lần đầu tiên sau khi sleep, server cần vài giây để khởi động
- Đợi vài giây rồi thử lại

## Lưu ý

- **Rate Limiting**: HuggingFace có giới hạn request, sử dụng hợp lý
- **Timeout**: Request dài có thể bị timeout
- **Cold Start**: Space sleep sau 48h không dùng, cần restart để wake up

## Tham khảo

- [README_vn.md](README_vn.md) - Tài liệu đầy đủ
- [HuggingFace Spaces Docs](https://huggingface.co/docs/hub/spaces)
- [MCP Protocol Docs](https://modelcontextprotocol.io/)
