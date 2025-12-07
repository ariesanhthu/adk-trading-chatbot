Trong MCP, client sẽ gọi theo **tên tool** (vd: `get_company_overview`) kèm params tương ứng.

**Lưu ý chung về `output_format`:**

* `output_format="json"` → hàm trả về **string JSON** theo dạng:

  ```json
  [
    { "col1": "...", "col2": "...", ... },
    ...
  ]
  ```

  Do `df.to_json(orient="records", force_ascii=False)`.

* `output_format="dataframe"` → trả về **pandas.DataFrame** (chỉ dùng được trong Python, không phải response HTTP thuần).

---

## 1. Company Tools

### 1.1. `get_company_overview`

**Mô tả:**
Lấy thông tin tổng quan (overview) của một cổ phiếu/doanh nghiệp (TCBS nguồn).

**Params:**

* `symbol` (str, bắt buộc): mã cổ phiếu, ví dụ: `"VNM"`, `"FPT"`.
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* Tạo `equity = TCBSCompany(symbol=symbol)`
* Gọi `equity.overview()` → DataFrame

**Return:**

* Nếu `output_format="json"`: JSON string dạng list các record overview.
* Nếu `"dataframe"`: `pd.DataFrame`

---

### 1.2. `get_company_news`

**Mô tả:**
Lấy tin tức (news) liên quan đến một công ty (TCBS nguồn).

**Params:**

* `symbol` (str, bắt buộc)
* `page_size` (int, mặc định `10`): số bản tin mỗi trang.
* `page` (int, mặc định `0`): index trang (0-based).
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `equity = TCBSCompany(symbol)`
* `df = equity.news(page_size=page_size, page=page)`

**Return:** JSON / DataFrame giống trên.

---

### 1.3. `get_company_events`

**Mô tả:**
Lấy các sự kiện của công ty (events: ĐHCĐ, chia cổ tức, phát hành thêm, …) từ TCBS.

**Params:**

* `symbol` (str)
* `page_size` (int, mặc định `10`)
* `page` (int, mặc định `0`)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Return:** JSON / DataFrame danh sách event.

---

### 1.4. `get_company_shareholders`

**Mô tả:**
Lấy thông tin cổ đông lớn / cơ cấu cổ đông công ty từ TCBS.

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Return:** JSON / DataFrame danh sách cổ đông.

---

### 1.5. `get_company_officers`

**Mô tả:**
Lấy danh sách ban điều hành / lãnh đạo, HĐQT, BKS… từ TCBS.

**Params:**

* `symbol` (str)
* `filter_by` (`"working" | "all" | "resigned"`, mặc định `"working"`):

  * `"working"`: chỉ người đang đương nhiệm
  * `"resigned"`: đã nghỉ
  * `"all"`: tất cả
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `equity = TCBSCompany(symbol)`
* `df = equity.officers(filter_by=filter_by)`

**Return:** JSON / DataFrame.

---

### 1.6. `get_company_subsidiaries`

**Mô tả:**
Lấy danh sách công ty con / công ty liên quan của doanh nghiệp từ TCBS.

**Params:**

* `symbol` (str)
* `filter_by` (`"all" | "subsidiary"`, mặc định `"all"`):

  * `"subsidiary"`: chỉ công ty con
  * `"all"`: toàn bộ (con, liên kết, …)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `equity = TCBSCompany(symbol)`
* `df = equity.subsidiaries(filter_by=filter_by)`

**Return:** JSON / DataFrame.

---

### 1.7. `get_company_reports`

**Mô tả:**
Lấy danh sách báo cáo phân tích / báo cáo doanh nghiệp từ VCI.

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `equity = VCICompany(symbol)`
* `df = equity.reports()`

**Return:** JSON / DataFrame (danh sách report: ngày, tiêu đề, link PDF, …).

---

### 1.8. `get_company_dividends`

**Mô tả:**
Lấy lịch sử cổ tức (dividend) của công ty từ TCBS.

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `equity = TCBSCompany(symbol)`
* `df = equity.dividends()`

**Return:** JSON / DataFrame (ngày chốt, ngày thanh toán, tỷ lệ, hình thức, …).

---

### 1.9. `get_company_insider_deals`

**Mô tả:**
Lấy giao dịch nội bộ (insider deals: cổ đông lớn, ban lãnh đạo giao dịch cổ phiếu) từ TCBS.

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `equity = TCBSCompany(symbol)`
* `df = equity.insider_deals()`

**Return:** JSON / DataFrame.

---

### 1.10. `get_company_ratio_summary`

**Mô tả:**
Lấy summary các chỉ số tài chính/định giá chính của doanh nghiệp (PE, PB, ROE, …) từ VCI.

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `equity = VCICompany(symbol)`
* `df = equity.ratio_summary()`

**Return:** JSON / DataFrame.

---

### 1.11. `get_company_trading_stats`

**Mô tả:**
Lấy thống kê giao dịch của cổ phiếu (turnover, volume, volatility, …) từ VCI.

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `equity = VCICompany(symbol)`
* `df = equity.trading_stats()`

**Return:** JSON / DataFrame.

---

## 2. Listing Tools

### 2.1. `get_all_symbol_groups`

**Mô tả:**
Trả về danh sách các group chỉ số/sàn với mã và mô tả.

**Params:**

* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* Tạo DataFrame từ list cứng:

  ```python
  [
    {"group": "HOSE", "group_name": "All symbols in HOSE"},
    {"group": "HNX", ...},
    ...
  ]
  ```

**Return:** JSON / DataFrame gồm các cột `group`, `group_name`.

---

### 2.2. `get_all_industries`

**Mô tả:**
Lấy danh sách ngành theo chuẩn ICB từ VCI.

**Params:**

* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `listing = VCIListing()`
* `df = listing.industries_icb()`

**Return:** JSON / DataFrame (mã ngành, tên ngành, cấp bậc ICB, …).

---

### 2.3. `get_all_symbols_by_group`

**Mô tả:**
Lấy danh sách mã cổ phiếu thuộc một group (HOSE, HNX, VN30, VN100,…).

**Params:**

* `group` (str, bắt buộc): ví dụ `"HOSE"`, `"VN30"`, `"VNMidCap"`, …
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `listing = VCIListing()`
* `df = listing.symbols_by_group(group=group)`

**Return:** JSON / DataFrame các mã thuộc group.

---

### 2.4. `get_all_symbols_by_industry`

**Mô tả:**
Lấy danh sách mã theo ngành ICB, hoặc toàn bộ nếu không truyền industry.

**Params:**

* `industry` (str | None, mặc định `None`):

  * Nếu `None` → trả tất cả.
  * Nếu có → filter theo các cột `icb_code1..4`.
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `listing = VCIListing()`
* `df = listing.symbols_by_industries()`
* Nếu `industry`:

  * Tạo mask từ `df[col].astype(str) == industry` cho `col` trong `["icb_code1","icb_code2","icb_code3","icb_code4"]` có mặt.
  * OR các mask rồi filter `df = df[mask]`.

**Return:** JSON / DataFrame.

---

### 2.5. `get_all_symbols`

**Mô tả:**
Lấy toàn bộ mã cổ phiếu theo sàn (exchange) từ VCI.

**Params:**

* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `listing = VCIListing()`
* `df = listing.symbols_by_exchange()`

**Return:** JSON / DataFrame.

---

## 3. Finance Tools

Dùng `VCIFinance(symbol=symbol, period=period)`.

### 3.1. `get_income_statements`

**Mô tả:**
Lấy báo cáo kết quả kinh doanh (Income Statement).

**Params:**

* `symbol` (str)
* `period` (`"quarter" | "year"`, mặc định `"year"`): chọn theo quý hay năm.
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `finance = VCIFinance(symbol, period)`
* `df = finance.income_statement()`

**Return:** JSON / DataFrame.

---

### 3.2. `get_balance_sheets`

**Mô tả:**
Lấy bảng cân đối kế toán (Balance Sheet).

**Params:**

* `symbol` (str)
* `period` (`"quarter" | "year"`, mặc định `"year"`)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `finance = VCIFinance(symbol, period)`
* `df = finance.balance_sheet()`

**Return:** JSON / DataFrame.

---

### 3.3. `get_cash_flows`

**Mô tả:**
Lấy báo cáo lưu chuyển tiền tệ (Cash Flow).

**Params:**

* `symbol` (str)
* `period` (`"quarter" | "year"`, mặc định `"year"`)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"` nhưng **code hiện tại không dùng**)

**Hoạt động:**

* `finance = VCIFinance(symbol, period)`
* `df = finance.cash_flow()`

**Return (THỰC TẾ):**

* Luôn trả về `df` (DataFrame), **không check `output_format`**.
  → Nếu bạn build HTTP wrapper, nên convert `df.to_json(...)` thủ công.

---

### 3.4. `get_finance_ratios`

**Mô tả:**
Lấy các chỉ số tài chính (Financial Ratios).

**Params:**

* `symbol` (str)
* `period` (`"quarter" | "year"`, mặc định `"year"`)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `finance = VCIFinance(symbol, period)`
* `df = finance.ratio()`

**Return:** JSON / DataFrame.

---

### 3.5. `get_raw_report`

**Mô tả:**
Lấy raw report từ VCI (dạng thô, không cấu trúc dễ đọc).

**Params:**

* `symbol` (str)
* `period` (`"quarter" | "year"`, mặc định `"year"`)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `finance = VCIFinance(symbol, period)`
* `df = finance._get_report(mode="raw")`

**Return:** JSON / DataFrame.

---

## 4. Fund Tools

Sử dụng `FMarketFund()`.

### 4.1. `list_all_funds`

**Mô tả:**
Liệt kê toàn bộ quỹ mở/quỹ đầu tư.

**Params:**

* `fund_type` (`"BALANCED" | "BOND" | "STOCK" | None`, mặc định `None`):

  * `None`: tất cả
  * `"BALANCED"`: quỹ cân bằng
  * `"BOND"`: quỹ trái phiếu
  * `"STOCK"`: quỹ cổ phiếu
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `fund = FMarketFund()`
* `df = fund.listing(fund_type=fund_type)`

**Return:** JSON / DataFrame.

---

### 4.2. `search_fund`

**Mô tả:**
Tìm kiếm quỹ theo keyword (tên/mã quỹ, partial match).

**Params:**

* `keyword` (str): chuỗi tìm kiếm (ví dụ `"VFM"`, `"SSIAM"` …)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `fund = FMarketFund()`
* `df = fund.filter(symbol=keyword)`

**Return:** JSON / DataFrame.

---

### 4.3. `get_fund_nav_report`

**Mô tả:**
Lấy báo cáo NAV lịch sử của quỹ.

**Params:**

* `symbol` (str): mã quỹ
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `fund = FMarketFund()`
* `df = fund.details.nav_report(symbol=symbol)`

**Return:** JSON / DataFrame.

---

### 4.4. `get_fund_top_holding`

**Mô tả:**
Lấy danh sách các khoản nắm giữ lớn nhất của quỹ (top holdings).

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `fund = FMarketFund()`
* `df = fund.details.top_holding(symbol=symbol)`

**Return:** JSON / DataFrame (tỷ trọng từng mã, ngành, …).

---

### 4.5. `get_fund_industry_holding`

**Mô tả:**
Lấy cơ cấu phân bổ theo ngành (industry allocation) của quỹ.

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `fund = FMarketFund()`
* `df = fund.details.industry_holding(symbol=symbol)`

**Return:** JSON / DataFrame.

---

### 4.6. `get_fund_asset_holding`

**Mô tả:**
Lấy cơ cấu phân bổ theo loại tài sản (asset allocation: equity, bond, cash, …).

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `fund = FMarketFund()`
* `df = fund.details.asset_holding(symbol=symbol)`

**Return:** JSON / DataFrame.

---

## 5. Misc Tools

### 5.1. `get_gold_price`

**Mô tả:**
Lấy giá vàng (SJC/BTMC).

**Params:**

* `date` (str | None, mặc định `None`):

  * Format: `"YYYY-MM-DD"`
  * Nếu `None`: lấy giá mới nhất từ SJC hoặc BTMC (tùy `source`).
  * Nếu có `date`: **code hiện tại luôn gọi `sjc_gold_price(date=date)` → bỏ qua `source`.**
* `source` (`"SJC" | "BTMC"`, mặc định `"SJC"`):

  * Chỉ có hiệu lực khi `date is None`.
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* Nếu `date`:

  * `price = sjc_gold_price(date=date)`
* Nếu không:

  * `price = sjc_gold_price()` nếu `source=="SJC"`
  * `price = btmc_goldprice()` nếu `source=="BTMC"`

**Return:** JSON / DataFrame.

---

### 5.2. `get_exchange_rate`

**Mô tả:**
Lấy tỷ giá ngoại tệ tại Vietcombank cho tất cả cặp.

**Params:**

* `date` (str | None, mặc định `None`):

  * Nếu `None`: dùng `datetime.now().strftime("%Y-%m-%d")`.
  * Format `"YYYY-MM-DD"`.
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `price = vcb_exchange_rate(date=date)`

**Return:** JSON / DataFrame (mã ngoại tệ, mua tiền mặt, mua chuyển khoản, bán, …).

---

## 6. Quote Tools

Dùng `Quote(symbol=symbol, source="VCI")`.

### 6.1. `get_quote_history_price`

**Mô tả:**
Lấy dữ liệu giá lịch sử (OHLCV) theo khoảng ngày & interval.

**Params:**

* `symbol` (str): mã chứng khoán.
* `start_date` (str, bắt buộc): `"YYYY-MM-DD"`
* `end_date` (str | None, mặc định `None`):

  * Nếu `None`: dùng ngày hiện tại (`datetime.now().strftime("%Y-%m-%d")`)
* `interval` (`"1m" | "5m" | "15m" | "30m" | "1H" | "1D" | "1W" | "1M"`, mặc định `"1D"`):

  * Khung thời gian dữ liệu.
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `quote = Quote(symbol, source="VCI")`
* `df = quote.history(start_date, end_date, interval)`

**Return:** JSON / DataFrame. Thường có cột: `time`, `open`, `high`, `low`, `close`, `volume`, …

---

### 6.2. `get_quote_intraday_price`

**Mô tả:**
Lấy dữ liệu giao dịch trong ngày (intraday ticks) cho một mã.

**Params:**

* `symbol` (str)
* `page_size` (int, mặc định `100`):

  * Docstring ghi `= 500 (max: 100000)` nhưng **thực tế default ở signature là 100**.
* `last_time` (str | None, mặc định `None`):

  * Thời điểm cuối cùng đã lấy (phục vụ phân trang theo thời gian, nếu lib hỗ trợ).
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `quote = Quote(symbol, source="VCI")`
* `df = quote.intraday(page_size=page_size, last_time=last_time)`

**Return:** JSON / DataFrame.

---

### 6.3. `get_quote_price_depth`

**Mô tả:**
Lấy dữ liệu độ sâu thị trường (orderbook: bid/ask levels) cho mã.

**Params:**

* `symbol` (str)
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `quote = Quote(symbol, source="VCI")`
* `df = quote.price_depth()`

**Return:** JSON / DataFrame (bảng bid/ask nhiều bước giá).

---

## 7. Trading Tools

### 7.1. `get_price_board`

**Mô tả:**
Lấy dữ liệu bảng giá cho nhiều mã cùng lúc.

**Params:**

* `symbols` (`list[str]`, bắt buộc):

  * Danh sách mã, ví dụ `["VNM", "FPT", "VCB"]`.
* `output_format` (`"json" | "dataframe"`, mặc định `"json"`)

**Hoạt động:**

* `trading = VCITrading()`
* `df = trading.price_board(symbols_list=symbols)`

**Return:** JSON / DataFrame. Thường gồm:

* Giá hiện tại, thay đổi, % thay đổi, khối lượng, giá tham chiếu, trần/sàn, …

