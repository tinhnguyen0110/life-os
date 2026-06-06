# Life OS — Architecture (full)

> **App:** Life OS — all-in-one life tracing OS (cá nhân, single-user, no-auth)
> **Stack:** Next.js (FE) · FastAPI (BE) · Markdown+git + SQLite (data) · APScheduler local
> **Chốt:** 2026-06-06
> **Triết lý:** App = nguồn sự thật (data). AI = bộ não NGOÀI (Claude Code), nối qua API/MCP sau. App tự đứng vững không cần AI. Mỗi feature là module độc lập, build riêng → nối qua interface chung. Mục tiêu #1: dễ mở rộng.

---

## 1. PATH

```
/home/watercry/Disk_C/Data/Tinhdev/
├── All-in-One Life/              # MOCK design reference (GIỮ NGUYÊN, bất biến)
│   └── Life Command/             #   data.js (schema gốc) + screens-*.js + app.css (design tokens)
└── life-os/                      # ⭐ APP THẬT — repo git riêng
```

App thật `life-os/` là repo độc lập — chính nó sau cũng là 1 dự án được track trong app (ăn dogfood).

---

## 2. STACK & QUYẾT ĐỊNH

| Lớp | Chọn | Lý do |
|---|---|---|
| Frontend | **Next.js** (App Router) | Bạn chọn; routing 14 screen + component sạch |
| Backend | **FastAPI** | API là trái tim; sau bọc FastMCP gần như free |
| Data — metadata | **Markdown + git** | Human + AI cùng đọc/ghi; git = lịch sử miễn phí; AI-native |
| Data — time-series | **SQLite** | Giá theo thời gian + run log cần query; markdown không hợp |
| Scheduler | **APScheduler (local)** | Bản đầu chạy local; sau chuyển GCP nếu cần 24/7 |
| AI | **NGOÀI (Claude Code)** | Không nhúng lúc này; nối qua API/MCP sau |

---

## 3. THƯ MỤC

```
life-os/
├── backend/
│   ├── core/
│   │   ├── base.py            # BaseModule interface (hợp đồng chung)
│   │   ├── registry.py        # auto-discover modules/ → gắn router vào app
│   │   ├── config.py          # settings, paths (DATA_DIR, DB_PATH, repo pointers)
│   │   └── scheduler.py       # APScheduler engine (cron + event listeners)
│   ├── modules/               # ⭐ mỗi feature = 1 module độc lập
│   │   ├── projects/          #   router.py · service.py · schema.py · reader.py
│   │   ├── finance/
│   │   ├── market/
│   │   ├── claude_usage/
│   │   ├── notes/
│   │   ├── journal/
│   │   ├── automation/        #   routines.py · run_log
│   │   ├── activity/
│   │   └── brief/             #   template-based brief (không AI)
│   ├── store/
│   │   ├── md_store.py        # đọc/ghi markdown + git commit
│   │   └── db.py              # SQLite (time-series, run log)
│   ├── data/                  # DATA_DIR — markdown thật (git-versioned)
│   │   ├── projects/<id>/     #   status.md · wiki.md · notes.md
│   │   ├── notes/
│   │   └── journal/
│   ├── main.py                # FastAPI app, registry.mount_all()
│   └── pyproject.toml
│
├── frontend/                  # Next.js
│   ├── app/                   # routes = 14 screen
│   │   ├── page.tsx           # S1 Home/Command Center
│   │   ├── projects/          # S2 list · [id] S3 detail
│   │   ├── graveyard/         # S4
│   │   ├── finance/           # S5 · portfolio/[id] S6
│   │   ├── journal/           # S7
│   │   ├── market/            # S8
│   │   ├── claude-usage/      # S9
│   │   ├── notes/             # S10
│   │   ├── brief/             # S11 (hiển thị, no chat)
│   │   ├── settings/          # S12
│   │   ├── routines/          # S13
│   │   └── activity/          # S14
│   ├── components/            # SHELL + dùng chung
│   │   ├── Sidebar · TopBar · CommandBar · TickerTape
│   │   ├── HealthChip · ProgressBar · KpiCard · DataTable · AlertRow · RingGauge · Sparkline
│   ├── features/              # ⭐ mỗi feature khớp module BE
│   │   ├── projects/ finance/ market/ claude-usage/ notes/ journal/ automation/ activity/
│   ├── lib/
│   │   ├── api.ts             # client gọi backend
│   │   ├── types.ts           # types khớp schema BE
│   │   └── tokens.css         # ⭐ port design tokens từ mock app.css (vars, themes, fonts)
│   └── package.json
│
└── README.md
```

---

## 4. INTERFACE CHUNG (cách module nối vào core)

Mỗi module BE phải có:
```
modules/<name>/
  router.py    # APIRouter — REST endpoints
  schema.py    # Pydantic models (data shape)
  service.py   # business logic
  reader.py    # (optional) đọc nguồn ngoài: git / giá / log
```

`core/base.py` định nghĩa hợp đồng:
```python
class BaseModule:
    name: str                      # "projects"
    router: APIRouter              # endpoints
    def routines(self) -> list: ...    # (optional) routine module này cấp cho scheduler
```

`core/registry.py`:
- Quét `modules/`, import mỗi module, lấy `router` → `app.include_router(prefix=f"/{name}")`
- Gom mọi `routines()` → đăng ký vào scheduler
→ **Thêm module mới = thêm 1 folder. Không sửa core, không sửa main.py.** Đây là điểm dễ-mở-rộng cốt lõi.

FE: mỗi `features/<name>/` tự chứa component + gọi `api.ts`. Screen (`app/`) ghép feature + shell.

---

## 5. FORMAT TRẠNG THÁI CHUNG (mọi reader trả về)

```
ProjectStatus = {
  id, name, desc, health: "act|slow|stall|dead", progress, users,
  last, lastDays, next, repo, metrics{commits, stars, lang, test_pass},
  routines[], lastAuto
}
```
Reader khác nhau (git/sprint/daemon log) → cùng output này → core + FE + AI xử lý 1 kiểu. (Schema gốc đã có sẵn trong mock `data.js`.)

---

## 6. DATA LAYER

- **Markdown + git** (`backend/data/`): mỗi dự án 1 folder `status.md · wiki.md · notes.md`; notes; journal. Mỗi lần ghi = 1 git commit → lịch sử miễn phí, AI đọc thẳng.
- **SQLite** (`backend/store/db.py`): bảng `price_history`, `run_log`, `claude_usage_history` — thứ cần query theo thời gian.
- **Ground truth = repo dự án ngoài** (DevCrew...), app chỉ TRỎ tới qua `config.py` pointer; reader đọc read-only, không sửa.

---

## 7. API SURFACE (FastAPI)

| Module | Endpoints |
|---|---|
| projects | `GET /projects` · `GET /projects/{id}` · `POST /projects/{id}/refresh` |
| finance | `GET /finance/overview` · `GET /finance/portfolio/{asset}` |
| market | `GET /market` · `GET /market/{asset}` · `GET /market/ticker` |
| claude_usage | `GET /claude-usage` |
| notes | `GET /notes` · `POST /notes` |
| journal | `GET /journal` · `POST /journal` |
| automation | `GET /routines` · `PATCH /routines/{id}` · `POST /routines/{id}/run` |
| activity | `GET /activity` |
| brief | `GET /brief` (template-based) |

Nguyên tắc: **raw-data first** (trả data thật + metadata); metric phái sinh (ladder state, "đứng yên bao lâu", lệch allocation) compute sẵn. Sau: FastMCP bọc routes → tool cho Claude Code.

---

## 8. DESIGN TOKENS (port từ mock — KHÔNG thiết kế lại)

Mock `app.css` đã có sẵn, chuyển thẳng vào `frontend/lib/tokens.css`:
- Base warm near-black: `--bg-0:#0f0a07 … --bg-3`
- Accent copper: `--accent:#FF6A33` + grad `linear-gradient(140deg,#ff9a5c,#e8451a)`
- Data roles: `--green:#34E08A` (sống) · `--red:#FF5C5C` (chết) · `--amber:#F5B43D` (chậm) · blue/violet
- Fonts: `--mono:'JetBrains Mono'` (mọi số) · `--sans:'Space Grotesk'` (UI)
- `--glow`, `--r:12px`, helper `.num .pos .neg .mid .acc .kicker`
- Themes (copper default) + scanline optional → port từ `shell.js THEMES/BG`
- Sparkline/area SVG helper → port từ `shell.js spark()`

Shell layout: `#app grid 228px 1fr` (collapsed 64px) — đúng sidebar thu gọn được.

---

## 9. THỨ TỰ IMPLEMENT (mỗi bước ship được độc lập)

| # | Bước | Nội dung | Ship được |
|---|---|---|---|
| **0** | Core + Shell | registry, BaseModule, FastAPI skeleton; FE shell (Sidebar/TopBar/CommandBar/Ticker) + port tokens.css | Khung chạy, navigate rỗng |
| **1** | **Projects** | BE router + git reader + FE bảng dự án (cột NEXT) + Detail | App thật đầu tiên, xuyên BE→API→FE |
| **2** | Market | giá real-time + ladder + ticker tape sống | Ticker + Market screen |
| **3** | Finance | portfolio, P&L, allocation (dùng market) | Finance + Portfolio screen |
| **4** | Claude Usage | ring + lịch sử (verify nguồn token) | Claude screen |
| **5** | Notes | markdown CRUD | Notes screen |
| **6** | Journal | form + calibration (dùng finance/market) | Journal screen |
| **7** | Automation + Activity | scheduler rule-based (poll/idle/pattern-check/nudge) + run log | Routines + Activity, app "active" |
| **8** | Graveyard + Brief | ghép từ projects data; brief = template | Home đầy đủ |
| **sau** | MCP + AI brief | FastMCP wrapper; brief do Claude Code sinh | Nối AI ngoài |

**Build rời rạc:** mỗi module BE chạy/test bằng curl độc lập; mỗi FE feature render route riêng. Khi xong → registry tự nhặt BE, thêm route FE vào sidebar. Có thể build song song nhiều module miễn giữ interface (router+schema).

---

## 10. ROUTINES BAN ĐẦU (rule-based, KHÔNG cần AI)

| Routine | Trigger | Hành động |
|---|---|---|
| market-poll | mỗi 5-15m | fetch giá → check ladder → alert |
| idle-hunter | mỗi tối | dự án đứng >N ngày → cảnh báo |
| pattern-check | hằng ngày | dự án ≥90% & 0 user → cảnh báo "build-to-90" |
| journal-nudge | khi giá chạm rung | nhắc ghi quyết định |
| wiki-refresh (metadata) | commit mới | reader đọc git → cập nhật status.md |
| morning-pull | 8h | pull mọi module → dựng brief template |

Giới hạn: ~6 routine có mục đích. KHÔNG xây skill-library. Routine cần AI sinh nội dung → hoãn tới khi nối Claude Code.

---

## 11. RANH GIỚI BẢN NÀY

- ✅ Build: 14 screen, 8 module, API mở, scheduler rule-based, command bar (lệnh action), brief template
- ❌ Không: chat AI nhúng, MCP, routine AI-generated, auth/multi-user/billing
- 🔜 Sau: FastMCP, AI brief Claude Code, GCP scheduler 24/7

---

## 12. LIÊN HỆ
- Spec tính năng đầy đủ: đã bàn (14 screen, S1-S14)
- Design baseline: mock `All-in-One Life/Life Command/` (đã duyệt màu+layout)
- Golden path tài chính (data cho Finance module): [[project_investment_golden_path]]
- Pattern build-to-90 (lý do tồn tại Graveyard/pattern-check): [[project_three_projects_strategy]]
```
