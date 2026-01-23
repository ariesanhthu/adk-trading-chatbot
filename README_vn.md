# VNStock MCP Server (Không chính thức)

[![Test Status](https://img.shields.io/badge/tests-passing-brightgreen?style=flat-square)](https://gitea.maobui.com/hypersense/vnstock-mcp-server/actions)
[![PyPI version](https://img.shields.io/pypi/v/vnstock-mcp-server?style=flat-square)](https://pypi.org/project/vnstock-mcp-server/)
[![PyPI downloads](https://img.shields.io/pypi/dm/vnstock-mcp-server?style=flat-square)](https://pypi.org/project/vnstock-mcp-server/)
[![Python versions](https://img.shields.io/pypi/pyversions/vnstock-mcp-server?style=flat-square)](https://pypi.org/project/vnstock-mcp-server/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

Một MCP (Model Context Protocol) server **không chính thức** cung cấp các công cụ để truy cập dữ liệu thị trường chứng khoán Việt Nam. Đây là một wrapper xung quanh thư viện [vnstock](https://github.com/thinh-vu/vnstock) tuyệt vời của [@thinh-vu](https://github.com/thinh-vu).

> **Lưu ý**: Đây là một dự án độc lập và không liên kết chính thức với thư viện vnstock hoặc các nhà phát triển của nó.

## Về vnstock

MCP server này được xây dựng dựa trên [thư viện vnstock](https://github.com/thinh-vu/vnstock) - một bộ công cụ Python mạnh mẽ để phân tích thị trường chứng khoán Việt Nam được tạo bởi Thinh Vũ. vnstock cung cấp quyền truy cập toàn diện vào dữ liệu thị trường chứng khoán Việt Nam bao gồm:

- Giá cổ phiếu theo thời gian thực và lịch sử
- Báo cáo tài chính của công ty
- Dữ liệu thị trường và thống kê giao dịch
- Thông tin quỹ đầu tư
- Giá vàng và tỷ giá hối đoái

Để biết thêm thông tin về thư viện gốc, truy cập: https://github.com/thinh-vu/vnstock

## Tính năng

MCP server này cung cấp các khả năng của vnstock thông qua các công cụ MCP, cho phép các trợ lý AI và các MCP client khác:

- Truy cập thông tin công ty và dữ liệu tài chính
- Lấy báo giá cổ phiếu và giá lịch sử
- Lấy thống kê giao dịch và dữ liệu thị trường
- Truy vấn thông tin quỹ đầu tư
- Truy cập giá vàng và tỷ giá hối đoái
- Lấy báo cáo tài chính (thu nhập, bảng cân đối kế toán, dòng tiền)

## Cài đặt

### Cài đặt từ PyPI (Được khuyến nghị)
```bash
pip install vnstock-mcp-server
```

### Cài đặt từ mã nguồn
```bash
git clone https://github.com/maobui/vnstock-mcp-server.git
cd vnstock-mcp-server
uv sync
```

## Yêu cầu
- Python 3.10+
- uv (cài đặt với `pip install uv` hoặc xem `https://docs.astral.sh/uv/`)

## Bắt đầu nhanh

### Chạy MCP server

#### Chế độ mặc định (stdio)
```bash
# Nếu cài đặt từ PyPI
vnstock-mcp-server

# Nếu cài đặt từ mã nguồn với uv
uv run python -m vnstock_mcp.server
```

#### Với các tùy chọn transport
```bash
# Sử dụng stdio transport (mặc định)
vnstock-mcp-server --transport stdio

# Sử dụng Server-Sent Events (SSE) transport cho ứng dụng web
vnstock-mcp-server --transport sse

# Sử dụng SSE với mount path tùy chỉnh
vnstock-mcp-server --transport sse --mount-path /vnstock

# Sử dụng HTTP streaming transport
vnstock-mcp-server --transport streamable-http

# Hiển thị trợ giúp với tất cả các tùy chọn có sẵn
vnstock-mcp-server --help
```

Server sử dụng `FastMCP` và hỗ trợ nhiều giao thức transport:
- **stdio**: Standard input/output (mặc định, cho các MCP client như Claude Desktop)
- **sse**: Server-Sent Events (cho ứng dụng web)
- **streamable-http**: HTTP streaming (cho tích hợp dựa trên HTTP)

## Chế độ Transport

VNStock MCP Server hỗ trợ ba giao thức transport khác nhau để phù hợp với các trường hợp sử dụng khác nhau:

### stdio (Mặc định)
- **Trường hợp sử dụng**: Các MCP client tiêu chuẩn như Claude Desktop, Cursor, Cline
- **Giao thức**: Giao tiếp qua luồng standard input/output
- **Sử dụng**: `vnstock-mcp-server` hoặc `vnstock-mcp-server --transport stdio`
- **Tốt nhất cho**: Ứng dụng desktop và tích hợp MCP truyền thống

### SSE (Server-Sent Events)
- **Trường hợp sử dụng**: Ứng dụng web cần streaming dữ liệu theo thời gian thực
- **Giao thức**: Server-sent events dựa trên HTTP
- **Sử dụng**: `vnstock-mcp-server --transport sse [--mount-path /path]`
- **Server chạy trên**: `http://127.0.0.1:8000` (mặc định)
- **Tốt nhất cho**: Dashboard web, ứng dụng dựa trên trình duyệt

### streamable-http
- **Trường hợp sử dụng**: Tích hợp dựa trên HTTP và dịch vụ API
- **Giao thức**: HTTP streaming với JSON-RPC over HTTP
- **Sử dụng**: `vnstock-mcp-server --transport streamable-http`
- **Server chạy trên**: `http://127.0.0.1:8000` (mặc định)
- **Tốt nhất cho**: Tích hợp REST API, kiến trúc microservices

### Tùy chọn dòng lệnh
```bash
vnstock-mcp-server [OPTIONS]

Tùy chọn:
  -t, --transport {stdio,sse,streamable-http}
                        Giao thức transport sử dụng (mặc định: stdio)
  -m, --mount-path MOUNT_PATH
                        Mount path cho SSE transport (tùy chọn)
  -v, --version         Hiển thị thông tin phiên bản
  -h, --help           Hiển thị thông báo trợ giúp
```

## Sử dụng MCP Server trên HuggingFace Spaces

VNStock MCP Server đã được deploy trên HuggingFace Spaces và có thể sử dụng trực tiếp qua SSE transport.

### Thông tin Deployment

- **URL HuggingFace Space**: `https://huggingface.co/spaces/Arischi05/mcp-vnstock`
- **Transport**: SSE (Server-Sent Events)
- **Port**: 7860 (port mặc định của HuggingFace Spaces)
- **Mount Path**: `/`

### Cách sử dụng

#### 1. Kiểm tra trạng thái server

Kiểm tra server có đang chạy không:

```bash
# Kiểm tra logs của server
curl -N \
     -H "Authorization: Bearer $HF_TOKEN" \
     "https://huggingface.co/api/spaces/Arischi05/mcp-vnstock/logs/run"
```

**Lưu ý**: Bạn cần có HuggingFace token. Lấy token tại: https://huggingface.co/settings/tokens

#### 2. Kết nối với MCP Server qua SSE

Server sử dụng SSE transport, bạn có thể kết nối qua các cách sau:

##### Sử dụng MCP Client (Python)

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
import httpx

# Kết nối với HuggingFace Space qua SSE
async with sse_client(
    "https://huggingface.co/spaces/Arischi05/mcp-vnstock/sse"
) as (read, write):
    async with ClientSession(read, write) as session:
        # Initialize session
        await session.initialize()
        
        # List available tools
        tools = await session.list_tools()
        print(f"Available tools: {len(tools.tools)}")
        
        # Call a tool (ví dụ: lấy thông tin công ty)
        result = await session.call_tool(
            "get_company_overview",
            arguments={"symbol": "VCB", "output_format": "json"}
        )
        print(result)
```

##### Sử dụng curl để test SSE endpoint

```bash
# Test SSE endpoint (streaming)
curl -N "https://huggingface.co/spaces/Arischi05/mcp-vnstock/sse"
```

##### Sử dụng JavaScript/TypeScript

```javascript
// Kết nối với SSE endpoint
const eventSource = new EventSource(
  'https://huggingface.co/spaces/Arischi05/mcp-vnstock/sse'
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
};
```

#### 3. Gọi các tools qua HTTP POST

Nếu server hỗ trợ HTTP endpoint, bạn có thể gọi tools trực tiếp:

```bash
# Ví dụ: Lấy thông tin công ty VCB
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

#### 4. Xem logs và debug

```bash
# Xem logs real-time
curl -N \
     -H "Authorization: Bearer $HF_TOKEN" \
     "https://huggingface.co/api/spaces/Arischi05/mcp-vnstock/logs/run"

# Xem logs của container
curl -N \
     -H "Authorization: Bearer $HF_TOKEN" \
     "https://huggingface.co/api/spaces/Arischi05/mcp-vnstock/logs/build"
```

#### 5. Restart server (nếu cần)

Nếu server gặp vấn đề, bạn có thể restart qua HuggingFace UI:
1. Vào https://huggingface.co/spaces/Arischi05/mcp-vnstock
2. Click vào menu "Settings" hoặc "..." 
3. Chọn "Restart this Space"

Hoặc qua API:

```bash
curl -X POST \
     -H "Authorization: Bearer $HF_TOKEN" \
     "https://huggingface.co/api/spaces/Arischi05/mcp-vnstock/restart"
```

### Các tools có sẵn

Server cung cấp các tools sau (tương tự như khi chạy local):

- **Company Tools**: `get_company_overview`, `get_company_news`, `get_company_events`, `get_company_shareholders`, v.v.
- **Finance Tools**: `get_income_statement`, `get_balance_sheet`, `get_cash_flow`, v.v.
- **Quote Tools**: `get_quote`, `get_price_history`, `get_price_board`, v.v.
- **Trading Tools**: `get_trading_data`, `get_order_book`, v.v.
- **Fund Tools**: `get_fund_list`, `get_fund_nav`, v.v.
- **Misc Tools**: `get_gold_price`, `get_exchange_rate`, v.v.

Xem chi tiết các tools trong phần "Các công cụ có sẵn" bên dưới.

### Lưu ý

1. **Rate Limiting**: HuggingFace Spaces có thể có giới hạn về số lượng request. Sử dụng hợp lý.
2. **Authentication**: Một số endpoint có thể yêu cầu HuggingFace token để truy cập.
3. **Cold Start**: Nếu Space không được sử dụng một thời gian, có thể mất vài giây để khởi động lại.
4. **Timeout**: Các request dài có thể bị timeout. Kiểm tra logs nếu gặp vấn đề.

### Troubleshooting

- **Server không phản hồi**: Kiểm tra logs và đảm bảo Space đang chạy (status = "Running")
- **Connection refused**: Space có thể đang trong trạng thái "Sleeping", cần restart
- **401 Unauthorized**: Đảm bảo bạn đã set `HF_TOKEN` environment variable đúng cách

## Tích hợp MCP client

### Ví dụ Cursor / Cline
Thêm một server entry trong cấu hình MCP của bạn:

#### Stdio transport mặc định
```json
{
  "mcpServers": {
    "vnstock": {
      "command": "uvx",
      "args": [
        "vnstock-mcp-server"
      ]
    }
  }
}
```

#### Với các tùy chọn transport cụ thể
```json
{
  "mcpServers": {
    "vnstock-sse": {
      "command": "uvx",
      "args": [
        "vnstock-mcp-server",
        "--transport",
        "sse",
        "--mount-path",
        "/vnstock"
      ]
    },
    "vnstock-http": {
      "command": "uvx",
      "args": [
        "vnstock-mcp-server",
        "--transport",
        "streamable-http"
      ]
    }
  }
}
```

Nếu cài đặt từ mã nguồn:
```json
{
  "mcpServers": {
    "vnstock": {
      "command": "uv",
      "args": ["run", "python", "-m", "vnstock_mcp.server"],
      "env": {}
    },
    "vnstock-sse": {
      "command": "uv",
      "args": ["run", "python", "-m", "vnstock_mcp.server", "--transport", "sse"],
      "env": {}
    }
  }
}
```

### Ví dụ Claude Desktop
Trong cài đặt MCP server:
- Command: `vnstock-mcp-server`
- Args: (để trống cho stdio, hoặc thêm tùy chọn transport như `--transport sse`)

## Các công cụ có sẵn

MCP server cung cấp các danh mục công cụ sau:

### Thông tin công ty
- Tổng quan công ty, tin tức, sự kiện
- Thông tin cổ đông và cán bộ
- Công ty con và giao dịch nội bộ
- Thống kê giao dịch và tỷ lệ

### Dữ liệu tài chính
- Báo cáo thu nhập, bảng cân đối kế toán, dòng tiền
- Tỷ lệ tài chính và báo cáo thô
- Dữ liệu tài chính lịch sử (theo quý/năm)

### Dữ liệu thị trường
- Báo giá theo thời gian thực và giá lịch sử
- Dữ liệu giao dịch trong ngày và độ sâu giá
- Bảng giá thị trường cho nhiều mã chứng khoán

### Thông tin quỹ
- Danh sách và tìm kiếm quỹ
- Báo cáo NAV và danh mục đầu tư
- Phân bổ ngành và tài sản

### Khác
- Giá vàng (SJC, BTMC)
- Tỷ giá hối đoái
- Danh sách mã chứng khoán theo ngành/nhóm

## Phát triển

### Cài đặt với uv (cho phát triển)
```bash
# Từ thư mục gốc dự án
uv sync

# Bao gồm dev dependencies (cho tests và coverage)
uv sync --group dev
```

### Kiểm thử với uv
```bash
# Chạy tất cả tests
uv run pytest

# Chạy một file test cụ thể
uv run pytest test/test_company_tools.py

# Chạy với coverage (HTML)
uv run pytest --cov=src/vnstock_mcp --cov-report=html
# Mở báo cáo:
#   ./htmlcov/index.html
```

### Build và Publish

#### Build cục bộ
```bash
# Sử dụng build script
./scripts/build.sh

# Hoặc thủ công
python -m build
```

#### Tạo một release
```bash
# Cập nhật version trong pyproject.toml trước, sau đó:
./scripts/release.sh
```

Điều này sẽ:
1. Chạy tests
2. Tạo và push một git tag
3. Kích hoạt GitHub Actions để build và publish lên PyPI

## Công nhận

Dự án này là một wrapper xung quanh [thư viện vnstock](https://github.com/thinh-vu/vnstock) được tạo bởi [@thinh-vu](https://github.com/thinh-vu). Tất cả chức năng truy cập dữ liệu thị trường chứng khoán được cung cấp bởi vnstock.

Vui lòng xem xét:
- ⭐ Đánh dấu sao [repository vnstock gốc](https://github.com/thinh-vu/vnstock)
- 📖 Đọc [tài liệu vnstock](https://vnstocks.com/docs)
- 💖 Hỗ trợ dự án vnstock nếu bạn thấy có giá trị

## Tuyên bố miễn trừ trách nhiệm

Đây là một wrapper không chính thức và không liên kết với thư viện vnstock hoặc các nhà phát triển của nó. Đối với các vấn đề liên quan đến dữ liệu thị trường chứng khoán cơ bản hoặc chức năng vnstock, vui lòng tham khảo [repository vnstock](https://github.com/thinh-vu/vnstock).

## Khắc phục sự cố

### Vấn đề cài đặt
- **Module không tìm thấy với `uv run`**:
  - Đảm bảo `uv sync` hoàn thành thành công trong thư mục gốc dự án.
  - Xác minh phiên bản Python: `python --version` và `uv python list`.
- **Lệnh `vnstock-mcp-server` không tìm thấy**:
  - Đảm bảo package đã được cài đặt: `pip list | grep vnstock-mcp-server`
  - Thử cài đặt lại: `pip install --upgrade vnstock-mcp-server`

### Vấn đề kết nối
- **MCP client không thể kết nối (chế độ stdio)**:
  - Xác nhận cấu hình client khớp với phương pháp cài đặt
  - Kiểm tra logs client để biết lỗi chi tiết.
  - Đảm bảo không có tham số bổ sung nào được truyền cho stdio transport
- **Không thể truy cập SSE/HTTP endpoints**:
  - Xác minh server đang chạy: kiểm tra "Uvicorn running on http://127.0.0.1:8000"
  - Kiểm tra xem port 8000 có khả dụng không: `netstat -an | grep 8000`
  - Thử truy cập `http://127.0.0.1:8000` trong trình duyệt cho chế độ SSE

### Vấn đề chế độ Transport
- **SSE transport không hoạt động**:
  - Đảm bảo mount-path được chỉ định đúng nếu cần
  - Kiểm tra server logs để biết lỗi khởi động
  - Xác minh web client có thể kết nối tới SSE endpoint
- **Chọn sai chế độ transport**:
  - Sử dụng `--help` để xem các tùy chọn transport có sẵn
  - stdio: cho desktop MCP clients (Claude Desktop, Cursor)
  - sse: cho ứng dụng web
  - streamable-http: cho tích hợp HTTP API

### Nhận trợ giúp
- **Kiểm tra phiên bản server**: `vnstock-mcp-server --version`
- **Xem tất cả tùy chọn**: `vnstock-mcp-server --help`
- **Kiểm tra khởi động server**: Chạy với `--transport stdio` trước để xác minh chức năng cơ bản

## Giấy phép

Giấy phép MIT - xem file [LICENSE](LICENSE) để biết chi tiết.

## Đóng góp

1. Fork repository
2. Tạo một feature branch
3. Thực hiện thay đổi của bạn
4. Thêm tests cho chức năng mới
5. Chạy tests: `uv run pytest`
6. Gửi một pull request

## Nhật ký thay đổi

### v1.1.0 (Phát triển hiện tại)
- **MỚI**: Thêm hỗ trợ cho nhiều chế độ transport (stdio, sse, streamable-http)
- **MỚI**: Tham số dòng lệnh để lựa chọn transport (`--transport`, `--mount-path`)
- **MỚI**: SSE (Server-Sent Events) transport cho ứng dụng web
- **MỚI**: HTTP streaming transport cho tích hợp API
- **CẢI TIẾN**: CLI nâng cao với thông báo trợ giúp và xác thực
- **CẢI TIẾN**: Xử lý lỗi tốt hơn và phản hồi người dùng
- **CẢI TIẾN**: Tài liệu toàn diện cho tất cả chế độ transport

### v1.0.0
- Phiên bản đầu tiên
- Truy cập đầy đủ dữ liệu thị trường chứng khoán Việt Nam qua MCP
- Hỗ trợ dữ liệu công ty, báo cáo tài chính, báo giá và nhiều hơn nữa
- Wrapper xung quanh vnstock v3.2.6+
