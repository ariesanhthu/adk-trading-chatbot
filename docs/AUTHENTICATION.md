# Authentication Guide - Hướng dẫn xác thực

Tài liệu này hướng dẫn cách xử lý authentication cho backend API.

---

## 1. Cấu hình Authentication Token

### 1.1. Thêm token vào `.env`

Thêm `BE_API_TOKEN` vào file `.env`:

```env
BE_API="https://ec2-3-25-106-203.ap-southeast-2.compute.amazonaws.com:4000/v1/api"
BE_API_TOKEN="your_jwt_token_here"
```

### 1.2. Lấy JWT Token

Có 2 cách để lấy token:

#### Cách 1: Login qua API

```bash
# POST /v1/api/auth/login
curl -X POST https://your-backend.com/v1/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'

# Response sẽ có accessToken
{
  "statusCode": 200,
  "metadata": {
    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "...",
    "user": {...}
  }
}
```

#### Cách 2: Google OAuth

1. User đăng nhập qua Google OAuth
2. Backend trả về `accessToken` và `refreshToken`
3. Lưu `accessToken` vào `.env` như `BE_API_TOKEN`

---

## 2. Endpoints yêu cầu Authentication

Theo `docs/API_ENDPOINTS.md`, các endpoints sau yêu cầu authentication (Auth: ✅):

| Endpoint                                                 | Method | Auth | Description           |
| -------------------------------------------------------- | ------ | ---- | --------------------- |
| `/stock-transactions/transactions/:transactionId`        | GET    | ✅   | Get transaction by ID |
| `/stock-transactions/transactions/:transactionId/cancel` | PUT    | ✅   | Cancel transaction    |
| `/stock-transactions/transactions/:userId/stats`         | GET    | ✅   | Get transaction stats |
| `/user/profile`                                          | GET    | ✅   | Get user profile      |

### Endpoints không cần Authentication (Auth: ❌):

| Endpoint                                   | Method | Auth | Description             |
| ------------------------------------------ | ------ | ---- | ----------------------- |
| `/stock-transactions/transactions`         | POST   | ❌   | Create transaction      |
| `/stock-transactions/transactions/:userId` | GET    | ❌   | Get transaction history |
| `/stock-transactions/ranking`              | GET    | ❌   | Get ranking             |

---

## 3. Cách sử dụng trong Code

### 3.1. Backend Tools (Agent)

Backend tools tự động thêm `Authorization` header nếu:

- Function có `require_auth=True`
- `BE_API_TOKEN` được set trong `.env`

**Example:**

```python
from agents.backend_tools import get_user_profile, get_transaction_stats

# Tự động thêm Authorization header
result = get_user_profile("69293046bcbc4ea01b8b76ce")
result = get_transaction_stats("69293046bcbc4ea01b8b76ce")

# Nếu thiếu token, sẽ trả về error:
# {
#   "error": "Authentication required",
#   "message": "This endpoint requires authentication but BE_API_TOKEN is not set...",
#   "suggestion": "Set BE_API_TOKEN in .env file with your JWT token"
# }
```

### 3.2. Test Script

Test script tự động thêm `Authorization` header cho các endpoints có `require_auth=True`:

```python
# test_transaction_api.py tự động thêm token cho:
# - test_get_transaction_stats (require_auth=True)
# - test_get_user_profile (require_auth=True)
```

**Chạy test:**

```bash
cd test-adk/scripts
python test_transaction_api.py
```

---

## 4. Error Handling

### 4.1. Missing Token

Nếu endpoint yêu cầu auth nhưng không có token:

```json
{
  "error": "Authentication required",
  "message": "This endpoint requires authentication but BE_API_TOKEN is not set in .env file.",
  "endpoint": "user/profile",
  "suggestion": "Set BE_API_TOKEN in .env file with your JWT token"
}
```

### 4.2. Invalid/Expired Token

Nếu token không hợp lệ hoặc đã hết hạn, backend sẽ trả về:

```json
{
  "statusCode": 401,
  "message": "Unauthorized - Token required"
}
```

**Giải pháp:**

1. Lấy token mới qua `/auth/login` hoặc `/auth/new-token`
2. Cập nhật `BE_API_TOKEN` trong `.env`

### 4.3. Refresh Token

Khi `accessToken` hết hạn, dùng `refreshToken` để lấy token mới:

```bash
# POST /v1/api/auth/new-token
curl -X POST https://your-backend.com/v1/api/auth/new-token \
  -H "Content-Type: application/json" \
  -d '{
    "refreshToken": "your_refresh_token_here"
  }'
```

---

## 5. Best Practices

### 5.1. Bảo mật Token

- ✅ **KHÔNG** commit `.env` vào Git (đã có trong `.gitignore`)
- ✅ **KHÔNG** log token ra console
- ✅ **KHÔNG** hardcode token trong code
- ✅ Sử dụng environment variables

### 5.2. Token Expiration

- `accessToken` thường có thời hạn ngắn (ví dụ: 15 phút - 1 giờ)
- `refreshToken` có thời hạn dài hơn (ví dụ: 7 ngày - 30 ngày)
- Tự động refresh token khi hết hạn (có thể implement trong tương lai)

### 5.3. Testing

- Test với token hợp lệ
- Test với token không hợp lệ
- Test với token hết hạn
- Test với missing token

---

## 6. Tài liệu liên quan

- `docs/API_ENDPOINTS.md`: Danh sách endpoints và yêu cầu auth
- `test-adk/agents/backend_tools.py`: Backend tools implementation
- `test-adk/scripts/test_transaction_api.py`: Test script với auth

---

## 7. Troubleshooting

### Lỗi: "Authentication required"

**Nguyên nhân:** Endpoint yêu cầu auth nhưng không có token.

**Giải pháp:**

1. Kiểm tra `BE_API_TOKEN` trong `.env`
2. Lấy token mới qua login API
3. Cập nhật `.env` với token mới

### Lỗi: "Unauthorized - Token required" (401)

**Nguyên nhân:** Token không hợp lệ hoặc đã hết hạn.

**Giải pháp:**

1. Lấy token mới qua `/auth/login` hoặc `/auth/new-token`
2. Cập nhật `BE_API_TOKEN` trong `.env`

### Lỗi: "Forbidden" (403)

**Nguyên nhân:** Token hợp lệ nhưng không có quyền truy cập endpoint.

**Giải pháp:**

1. Kiểm tra quyền của user
2. Liên hệ admin để cấp quyền

---

## 8. Changelog

### 2024-12-06

- ✅ Thêm hỗ trợ `BE_API_TOKEN` trong `.env`
- ✅ Backend tools tự động thêm `Authorization` header
- ✅ Test script hỗ trợ authentication
- ✅ Error handling cho missing/invalid token
