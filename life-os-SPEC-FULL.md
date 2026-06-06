# Life OS — Đặc tả Tính năng Toàn diện

> **App:** Life OS — all-in-one life tracing OS cá nhân
> **Cho ai:** chỉ mình tôi (single-user, no-auth, no-billing)
> **Chốt:** 2026-06-06
> **Kiến trúc/stack:** xem `life-os-ARCHITECTURE.md` · **Design baseline:** mock `All-in-One Life/Life Command/`

---

## 0. MỤC ĐÍCH HỆ THỐNG

**Một câu:** Trung tâm điều hành cuộc sống số của tôi — theo dõi dự án, tài chính/đầu tư, Claude Code usage, ghi chú; tự vận hành (automation) theo rule tôi đặt; mở API để AI ngoài (Claude Code) cắm vào lấy data thật và tư vấn.

**App giải quyết 3 vấn đề thật:**
1. **Mất dấu dự án** — tôi build nhiều thứ, không biết cái nào sống/chết, đang ở đâu, ai dùng.
2. **Pattern build-to-90 rồi bỏ** — tôi xây tới ~90% rồi bỏ, 0 user. App phải SOI và CHẶN pattern này.
3. **Phân mảnh** — tiền, dự án, quota AI, note nằm rải rác. Cần 1 chỗ nhìn hết.

**4 câu app phải trả lời cho mỗi dự án:** Đang ở đâu? / Mục tiêu gì? / Ai đang dùng? / Bước tiếp theo?

**Nguyên tắc cốt lõi:**
- App = **nguồn sự thật** (data thật + metadata). AI = **bộ não NGOÀI** (Claude Code), thay thế được.
- **Ref-không-embed:** dự án thật sống ở repo riêng; app chỉ trỏ tới + giữ metadata.
- **API là trái tim:** mọi screen + AI đọc qua API.
- **Raw-data first:** app trả data thật; suy luận để AI làm.
- **Active OS:** tôi define rule + goal, app tự chạy; minh bạch qua Activity Feed.
- **Honest mirror:** app dám nói thẳng sự thật (quyết bỏ?, pattern 90%-0-user).

---

## 1. KHUNG GIAO DIỆN CHUNG (mọi screen)

| Thành phần | Mục đích | Tính năng |
|---|---|---|
| **Sidebar** (trái, thu gọn được) | Điều hướng | 6 nhóm: Tổng quan / Dự án / Tài chính / Hằng ngày / Hệ thống(Tự động) / Cấu hình. Mỗi mục badge số. Logo + avatar user. Nút thu gọn icon-only. |
| **Top bar** | Trạng thái + hành động | Breadcrumb screen · `API live` · `Sync N phút trước` · nút Refresh · chuông cảnh báo (badge số) |
| **Command bar** | Cockpit điều khiển | Input prefix `>`: gõ lệnh action (`dca btc 2000`, `open <project>`, `note ...`, `run <routine>`) + nhảy nhanh. ⌘K mở palette. (KHÔNG hỏi AI trong app bản này) |
| **Ticker tape** (đáy, cố định) | Thị trường liếc nhanh | Dải mono chạy: BTC·ETH·SOL·SPY·QQQ·VNINDEX·USDT/VND·Brent·Gold. Xanh tăng/đỏ giảm. |

---

## 2. CÁC SCREEN & TÍNH NĂNG (S1–S14)

### S1 — Command Center (Home)
**Mục đích:** Mở mỗi sáng, 1 màn hình thấy hết đời sống số + biết hôm nay làm gì.
**Tính năng:**
- KPI strip: **Tổng tài sản** (số lớn + thay đổi ngày/tuần + area chart + thanh phân bổ kênh) · **P&L theo kênh** (list số) · **Claude quota** (ring %)
- **Bảng dự án đang chạy** — cột: Dự án / Sức khỏe / Tiến độ / Users / Hoạt động / **NEXT**. Footer đếm trạng thái + "+ thêm dự án"
- **Brief hôm nay** (template + data thật) — danh sách đánh số ưu tiên
- **Cảnh báo nổi** — list dot + nguồn + thời gian
- Click widget → screen chi tiết; click dòng dự án → Detail; click alert → nguồn

### S2 — Projects List
**Mục đích:** Toàn bộ dự án, biết cái nào sống/chết.
**Tính năng:**
- Thanh tóm tắt: tổng + đếm theo trạng thái (active/chậm/đứng/bỏ)
- Bảng/card mỗi dự án: tên, mô tả, tiến độ %, mục tiêu, users, sức khỏe, hoạt động cuối, cột NEXT
- **Badge cảnh báo 90%-0-user**
- Filter theo trạng thái · Sort (tiến độ/hoạt động/users)
- Nút thêm dự án (khai con trỏ repo + mục tiêu)

### S3 — Project Detail
**Mục đích:** Hiểu sâu 1 dự án, trả lời 4 câu cốt lõi.
**Tính năng:**
- Header: tên, sức khỏe, mục tiêu/North Star, link repo
- 4 câu trả lời nổi bật: đang đâu / mục tiêu / ai dùng / bước tiếp
- Tiến độ + nguồn · Metric: commits, stars, lang, test pass %, users, "đứng yên bao lâu"
- **Wiki dự án** (là gì, kiến trúc, đang làm gì, kẹt đâu)
- Timeline lịch sử cập nhật
- Notes dự án (tôi + AI cùng ghi)
- Bước tiếp theo (đề xuất + chỉnh sửa)
- Routine đang gắn + lần auto-refresh cuối
- Nút: refresh từ repo · đánh dấu đã bỏ (→ Graveyard, ghi lý do + mức %)

### S4 — Graveyard (Nghĩa địa)
**Mục đích:** Nhìn thẳng pattern bỏ dở, không giấu.
**Tính năng:**
- Danh sách dự án đã bỏ: tên, bỏ ở mức %, ngày, lý do, **bài học**
- Thống kê pattern: TB bỏ ở mức %, lý do hay gặp, số dự án đạt-user vs bỏ-trước-user
- Đối chiếu pattern cá nhân (build-to-90)
- Phục hồi dự án về active (tùy chọn)

### S5 — Finance Overview
**Mục đích:** Toàn cảnh tài chính + đầu tư.
**Tính năng:**
- Tổng tài sản + thay đổi
- Phân bổ danh mục theo kênh (Crypto/ETF/VN/Dry) + tỷ trọng
- **So target allocation** (golden path) — lệch bao nhiêu + cảnh báo lệch
- Giá trị portfolio theo thời gian (chart)
- P&L tổng + theo kênh
- Dry powder còn lại + lương dự kiến vào
- Trạng thái golden path (rung ladder, signal active)
- Click kênh → Portfolio Detail

### S6 — Portfolio Detail (1 kênh)
**Mục đích:** Đào sâu 1 kênh, ra quyết định vào/không.
**Tính năng:**
- Giá hiện tại + thay đổi
- Vị thế: đã vào, giá vốn TB, P&L
- **Ladder state**: rung đã vào / rung tiếp + giá trigger / còn cách bao xa
- Signal liên quan: oil override, ETF flows, CPI/Fed (crypto); FTSE catalyst (VN)
- Chart giá + đánh dấu điểm mua + mức trigger
- Note riêng kênh · Liên kết journal (lệnh đã ghi)
- Trạng thái "vào được chưa" (data thật) · Nút ghi quyết định → Journal

### S7 — Investment Journal
**Mục đích:** Biến quyết định đầu tư thành dữ liệu học (calibration).
**Tính năng:**
- Form ghi: thesis, điều kiện phủ định, size, confidence %, kênh, ngày
- Danh sách lệnh (lọc kênh/thời gian)
- **Review hàng tháng: chấm calibration** (confidence 70% có đúng ~70%)
- Track process tách P&L (có theo luật không)
- Đối chiếu kết quả sau khi đóng vị thế: thesis đúng/sai + bài học
- Nhắc review định kỳ

### S8 — Market & Alerts
**Mục đích:** Giá + tín hiệu + lịch sử cảnh báo 1 chỗ.
**Tính năng:**
- Giá real-time các tài sản theo dõi
- **Bảng trigger**: ngưỡng đã chạm / sắp chạm (còn cách bao xa)
- **Signal vĩ mô**: Brent/oil, CPI, Fed, ETF flows + trạng thái
- Lịch sử alert đã bắn
- Cấu hình ngưỡng alert per-asset
- Bắn alert qua: desktop / Discord / in-app

### S9 — Claude Usage
**Mục đích:** Theo dõi quota Claude Code dùng hằng ngày.
**Tính năng:**
- Token đã dùng / còn lại / % đốt
- **Đếm ngược reset** (5h window + weekly)
- Lịch sử usage theo ngày/tuần (chart)
- Cảnh báo sắp hết quota
- (Nguồn data: file config/log local Claude Code — verify khi build; fallback nhập tay)

### S10 — Notes
**Mục đích:** Ghi chú all-in-one, AI đọc cùng nguồn.
**Tính năng:**
- Tạo/sửa note nhanh (markdown)
- Gắn note vào: dự án / kênh / đứng riêng
- Tag + tìm kiếm · Daily log
- Note gắn dự án hiển thị trong Project Detail
- Lưu dạng markdown (chung nguồn data, AI đọc được)

### S11 — Brief
**Mục đích:** Báo cáo tổng hợp hằng ngày (KHÔNG chat AI trong app).
**Tính năng:**
- **Morning brief tự sinh** (template + data thật): tóm tắt tài sản + dự án + claude + cảnh báo + ưu tiên
- Lịch sử brief
- (Sau: brief do Claude Code ngoài sinh; chat làm qua Claude Code)

### S12 — Settings / Registry
**Mục đích:** Cấu hình toàn hệ — thêm dự án/kênh không cần sửa code.
**Tính năng:**
- **Quản lý dự án (registry):** thêm/sửa con trỏ repo, mục tiêu, reader bật, mô tả
- **Quản lý kênh đầu tư:** thêm kênh, target allocation, giá vốn, vị thế
- Cấu hình nguồn giá + ngưỡng trigger per-asset
- Cấu hình alert channel (desktop/Discord/in-app)
- Cấu hình Claude usage source
- Tweak giao diện (theme accent, density, scanline) — đã có sẵn trong mock

### S13 — Routines (Automation)
**Mục đích:** Tôi define rule + goal, app tự chạy. Lớp "active".
**Tính năng:**
- Danh sách routine: tên, trigger, hành động, on/off, lần chạy cuối, kết quả
- **3 loại trigger:** Scheduled (cron) · Event (commit/giá/idle) · On-demand (bấm chạy)
- Bật/tắt từng routine · Tạo/sửa routine (form: trigger + action + params)
- Xem lịch sử chạy (→ Activity Feed)
- **Bộ routine khởi đầu (rule-based, không AI):**
  - `market-poll` — mỗi 5-15m → fetch giá → check ladder → alert
  - `idle-hunter` — mỗi tối → dự án đứng >N ngày → cảnh báo
  - `pattern-check` — hằng ngày → dự án ≥90% & 0 user → cảnh báo build-to-90
  - `journal-nudge` — khi giá chạm rung → nhắc ghi quyết định
  - `wiki-refresh` — commit mới → reader cập nhật status/metadata
  - `morning-pull` — 8h → pull mọi module → dựng brief
- Giới hạn: ~6 routine có mục đích. KHÔNG skill-library.

### S14 — Activity Feed (Run Log)
**Mục đích:** Minh bạch — automation/AI vừa làm gì. Chống hộp đen.
**Tính năng:**
- Feed thời gian thực: ✓/✗ tên routine, mô tả, thời gian, kết quả
- Trạng thái mỗi run (thành công/lỗi/đang chạy)
- Xem chi tiết log + output 1 run
- Filter theo routine/trạng thái · Đếm số run hôm nay
- Widget rút gọn ở Home

---

## 3. API LAYER (trái tim)

**Mục đích:** mọi screen + AI ngoài đọc qua đây. App đứng độc lập không cần FE.
**Endpoints chính:**
- projects: list / detail / refresh
- finance: overview / portfolio/{asset}
- market: list / {asset} / ticker
- claude-usage / notes (CRUD) / journal (CRUD)
- automation: routines / toggle / run · activity: feed
- brief: template-based
**Nguyên tắc:** raw-data first; metric phái sinh compute sẵn (ladder state, "đứng yên bao lâu", lệch allocation, calibration). Sau: FastMCP bọc routes → tool cho Claude Code.

---

## 4. DATA LAYER

- **Markdown + git:** metadata dự án (status/wiki/notes), notes, journal. Mỗi ghi = 1 commit (lịch sử miễn phí, AI đọc thẳng).
- **SQLite:** time-series (giá, run log, claude usage history) — thứ cần query theo thời gian.
- **Ground truth:** repo dự án ngoài (DevCrew...), app trỏ tới, reader đọc read-only.
- **Format trạng thái chung:** mọi reader trả `{id, name, health, progress, users, last, lastDays, next, repo, metrics, routines, lastAuto}`.

---

## 5. COLOR + TYPOGRAPHY (port từ mock, không thiết kế lại)

| Vai | Màu |
|---|---|
| Nền warm near-black | `--bg-0:#0f0a07 … --bg-3` |
| Accent copper (nhấn/brand/action) | `--accent:#FF6A33` + grad `140deg,#ff9a5c,#e8451a` |
| Green = sống/tích cực | `#34E08A` |
| Đỏ = chết/giảm/cảnh báo | `#FF5C5C` |
| Amber = chậm/chú ý | `#F5B43D` |
| Phụ blue/violet | `#4DA6FF` / `#a877ff` |
- Mono `JetBrains Mono` (mọi số/ticker/%/lệnh) · Sans `Space Grotesk` (UI)
- Nhãn tiếng Việt + thuật ngữ English (token, P&L, ladder, MRR)
- Sidebar grid 228px / collapsed 64px · radius 12px · glow nhẹ ở accent

---

## 6. RANH GIỚI BẢN NÀY (build) vs SAU

| Phần | Bản này | Sau |
|---|---|---|
| Tracing / Finance / Claude / Notes / Journal | ✅ | |
| API mở (FastAPI) | ✅ | → FastMCP |
| Command bar | ✅ lệnh action | + hỏi AI |
| Brief | ✅ template + data thật | → Claude Code sinh |
| Automation + Activity | ✅ rule-based | + routine AI |
| Chat AI nhúng / MCP / auth-billing | ❌ | ✅ (MCP) |

---

## 7. TÓM 14 SCREEN

| Nhóm | Screen |
|---|---|
| Tổng quan | S1 Command Center |
| Dự án | S2 Projects · S3 Detail · S4 Graveyard |
| Tài chính | S5 Finance · S6 Portfolio · S7 Journal · S8 Market&Alerts |
| Hằng ngày | S9 Claude Usage · S10 Notes |
| Hệ thống | S13 Routines · S14 Activity Feed |
| Cấu hình | S11 Brief · S12 Settings |

---

## 8. LIÊN HỆ
- Kiến trúc kỹ thuật: `life-os-ARCHITECTURE.md`
- Design mock (đã duyệt): `All-in-One Life/Life Command/`
- Data Finance: golden path `project_investment_golden_path`
- Lý do tồn tại Graveyard/pattern-check: pattern build-to-90 `project_three_projects_strategy`
