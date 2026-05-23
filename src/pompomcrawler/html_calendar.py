from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

from .extract import merge_duplicates
from .models import ScheduleItem
from .schedule_window import DEFAULT_PAST_DAYS, filter_schedule_window, parse_iso_date, primary_date


KIND_LABELS = {
    "product": "商品",
    "event": "イベント",
    "campaign": "キャンペーン",
    "reservation": "予約",
    "other": "その他",
}

STATUS_LABELS = {
    "candidate": "候補",
    "needs_review": "確認待ち",
    "confirmed": "確認済み",
    "excluded": "除外",
}


def export_calendar_html(
    items: list[ScheduleItem],
    output_dir: Path = Path("outputs"),
    *,
    filter_window: bool = True,
    past_days: int = DEFAULT_PAST_DAYS,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    merged = merge_duplicates(items)
    if filter_window:
        merged = filter_schedule_window(merged, past_days=past_days)
    payload = [calendar_item(item, index) for index, item in enumerate(merged, start=1)]
    path = output_dir / "pompompurin_calendar.html"
    path.write_text(render_html(payload, past_days=past_days, filter_window=filter_window), encoding="utf-8")
    return path


def calendar_item(item: ScheduleItem, index: int) -> dict:
    return {
        "id": index,
        "title": item.title,
        "kind": item.kind or "other",
        "kindLabel": KIND_LABELS.get(item.kind, item.kind or "その他"),
        "status": item.status,
        "statusLabel": STATUS_LABELS.get(item.status, item.status),
        "startDate": normalize_date(item.start_date),
        "endDate": normalize_date(item.end_date),
        "releaseDate": normalize_date(item.release_date),
        "reservationStart": normalize_date(item.reservation_start),
        "primaryDate": primary_date(item),
        "sellerOrVenue": item.seller_or_venue,
        "sourceUrl": item.source_url,
        "sourceName": item.source_name,
        "confidence": round(item.confidence, 2),
        "reviewReason": item.review_reason,
        "notes": item.notes,
    }


def normalize_date(value: str) -> str:
    parsed = parse_iso_date(value)
    return parsed.isoformat() if parsed else ""


def render_html(items: list[dict], *, past_days: int, filter_window: bool) -> str:
    data_json = json.dumps(items, ensure_ascii=False)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    window_text = f"直近{past_days}日＋未来" if filter_window else "全期間"
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ポムポムプリン予定帳</title>
  <style>
    :root {{
      color-scheme: light;
      --page: #fff8e6;
      --cream: #fffdf5;
      --custard: #ffe08a;
      --custard-soft: #fff0bd;
      --caramel: #7a4b27;
      --cocoa: #352417;
      --muted: #7d6858;
      --line: #ead7b3;
      --mint: #47b9a9;
      --mint-soft: #e1f7f2;
      --berry: #f57b98;
      --sky: #74b7e8;
      --leaf: #7fb96d;
      --lavender: #b79be8;
      --shadow: 0 18px 44px rgba(92, 60, 31, .13);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at 12px 12px, rgba(122, 75, 39, .08) 0 2px, transparent 2.5px),
        linear-gradient(135deg, #fff7d7 0%, #fffaf0 44%, #e9f8f4 100%);
      background-size: 28px 28px, auto;
      color: var(--cocoa);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    button, input, select {{ font: inherit; }}
    a {{ color: inherit; }}
    .app-shell {{ min-height: 100vh; }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      background: rgba(255, 248, 230, .86);
      border-bottom: 1px solid rgba(122, 75, 39, .12);
      backdrop-filter: blur(18px) saturate(1.18);
    }}
    .topbar-inner {{
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 18px 20px;
      display: grid;
      grid-template-columns: minmax(260px, 1fr) auto;
      gap: 16px;
      align-items: center;
    }}
    .brand {{
      display: grid;
      grid-template-columns: 64px minmax(0, 1fr);
      gap: 14px;
      align-items: center;
      min-width: 0;
    }}
    .pudding-mark {{
      width: 64px;
      height: 64px;
      filter: drop-shadow(0 12px 18px rgba(122, 75, 39, .18));
    }}
    .brand h1 {{
      margin: 0;
      font-size: clamp(22px, 2.4vw, 34px);
      letter-spacing: 0;
      line-height: 1.15;
      color: var(--caramel);
    }}
    .brand p {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}
    .month-controls {{
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
    }}
    .icon-button, .text-button {{
      min-height: 42px;
      border: 1px solid rgba(122, 75, 39, .16);
      background: rgba(255, 253, 245, .94);
      color: var(--caramel);
      cursor: pointer;
      box-shadow: 0 8px 18px rgba(122, 75, 39, .09);
    }}
    .icon-button {{
      width: 42px;
      display: inline-grid;
      place-items: center;
      border-radius: 8px;
      font-size: 24px;
      line-height: 1;
    }}
    .text-button {{
      border-radius: 8px;
      padding: 0 16px;
      font-weight: 900;
    }}
    .icon-button:hover, .text-button:hover {{
      border-color: var(--mint);
      transform: translateY(-1px);
    }}
    .layout {{
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 22px 20px 38px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 20px;
      align-items: start;
    }}
    .toolbar {{
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: minmax(220px, 1fr) repeat(2, minmax(150px, 190px)) auto;
      gap: 12px;
      align-items: center;
      padding: 12px;
      background: rgba(255, 253, 245, .68);
      border: 1px solid rgba(122, 75, 39, .12);
      border-radius: 8px;
      box-shadow: 0 12px 30px rgba(122, 75, 39, .08);
    }}
    .field {{
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 46px;
      padding: 0 14px;
      border: 1px solid rgba(122, 75, 39, .13);
      background: #fffef9;
      border-radius: 8px;
    }}
    .field span {{
      color: var(--caramel);
      font-size: 12px;
      font-weight: 900;
    }}
    .field input, .field select {{
      width: 100%;
      min-width: 0;
      border: 0;
      outline: 0;
      background: transparent;
      color: var(--cocoa);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      grid-column: 1 / -1;
    }}
    .stat {{
      background: rgba(255, 253, 245, .76);
      border: 1px solid rgba(122, 75, 39, .1);
      border-radius: 8px;
      padding: 13px 14px;
      min-width: 0;
      box-shadow: 0 10px 24px rgba(122, 75, 39, .07);
    }}
    .stat strong {{
      display: block;
      font-size: 26px;
      line-height: 1;
      color: var(--caramel);
    }}
    .stat span {{
      display: block;
      margin-top: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }}
    .calendar-panel, .side-panel {{
      background: rgba(255, 253, 245, .92);
      border: 1px solid rgba(122, 75, 39, .13);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .calendar-head {{
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      border-bottom: 1px solid rgba(122, 75, 39, .13);
      background: linear-gradient(90deg, #ffe9a4, #dff7f0);
    }}
    .weekday {{
      padding: 11px 8px;
      color: var(--caramel);
      font-size: 12px;
      font-weight: 900;
      text-align: center;
    }}
    .calendar-grid {{
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
    }}
    .mobile-schedule {{
      display: none;
    }}
    .day {{
      min-height: 136px;
      padding: 9px;
      border-right: 1px solid rgba(122, 75, 39, .1);
      border-bottom: 1px solid rgba(122, 75, 39, .1);
      background: rgba(255, 255, 250, .94);
      overflow: hidden;
    }}
    .day:nth-child(7n) {{ border-right: 0; }}
    .day.is-muted {{
      background: rgba(255, 248, 228, .55);
      color: #a68b75;
    }}
    .day.is-today {{
      background: linear-gradient(180deg, #fff2b7, #e7f9f4);
      box-shadow: inset 0 0 0 3px var(--mint), inset 0 0 0 6px rgba(255, 255, 255, .8);
    }}
    .day-number {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 6px;
      font-weight: 800;
      font-size: 13px;
    }}
    .day.is-today .day-number span:first-child {{
      width: 30px;
      height: 30px;
      display: inline-grid;
      place-items: center;
      border-radius: 999px;
      background: var(--caramel);
      color: #fff;
      box-shadow: 0 6px 14px rgba(122, 75, 39, .24);
    }}
    .day-count {{
      min-width: 22px;
      height: 22px;
      display: inline-grid;
      place-items: center;
      border-radius: 999px;
      background: var(--mint-soft);
      color: #167c70;
      font-size: 12px;
      font-weight: 900;
    }}
    .event-list {{
      display: grid;
      gap: 5px;
    }}
    .event-pill {{
      display: block;
      width: 100%;
      min-height: 32px;
      padding: 6px 8px;
      border: 0;
      border-left: 4px solid var(--mint);
      border-radius: 6px;
      background: var(--mint-soft);
      color: var(--cocoa);
      text-align: left;
      cursor: pointer;
      overflow: hidden;
      box-shadow: 0 4px 10px rgba(53, 36, 23, .05);
    }}
    .event-pill strong {{
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 12px;
      letter-spacing: 0;
    }}
    .event-pill span {{
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--muted);
      font-size: 11px;
    }}
    .event-pill.product {{ border-left-color: var(--caramel); background: #fff0bf; }}
    .event-pill.event {{ border-left-color: var(--sky); background: #eaf5ff; }}
    .event-pill.campaign {{ border-left-color: var(--berry); background: #ffeaf0; }}
    .event-pill.reservation {{ border-left-color: var(--leaf); background: #ecf8e9; }}
    .more-button {{
      width: 100%;
      border: 0;
      background: transparent;
      color: #167c70;
      cursor: pointer;
      font-weight: 800;
      font-size: 12px;
      text-align: left;
      padding: 2px 0;
    }}
    .side-panel {{
      position: sticky;
      top: 104px;
      max-height: calc(100vh - 112px);
      display: flex;
      flex-direction: column;
    }}
    .side-header {{
      padding: 16px;
      border-bottom: 1px solid rgba(122, 75, 39, .12);
      background: linear-gradient(135deg, #ffe9a4, #e7f8f4);
    }}
    .side-header h2 {{
      margin: 0;
      color: var(--caramel);
      font-size: 18px;
      letter-spacing: 0;
    }}
    .side-header p {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }}
    .agenda {{
      padding: 6px 14px 14px;
      overflow: auto;
    }}
    .agenda-item {{
      border-bottom: 1px solid rgba(122, 75, 39, .12);
      padding: 14px 2px;
      background: transparent;
      cursor: pointer;
    }}
    .agenda-item:last-child {{ border-bottom: 0; }}
    .agenda-item h3 {{
      margin: 0;
      font-size: 15px;
      line-height: 1.35;
      letter-spacing: 0;
      color: var(--cocoa);
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 8px 0;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      background: #fff0bf;
      color: var(--caramel);
      font-size: 12px;
      font-weight: 700;
    }}
    .tag.review {{ background: #ffe7a1; }}
    .tag.confirmed {{ background: #dff4e7; color: #2f7652; }}
    .tag.excluded {{ background: #eee8dc; color: #8d7b68; }}
    .detail-text {{ margin: 0; color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }}
    .source-link {{
      display: inline-block;
      margin-top: 10px;
      color: #167c70;
      font-weight: 800;
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .empty {{
      padding: 28px 14px;
      color: var(--muted);
      text-align: center;
    }}
    .mobile-day-card {{
      border: 1px solid rgba(122, 75, 39, .13);
      border-radius: 8px;
      background: rgba(255, 253, 245, .92);
      box-shadow: 0 10px 24px rgba(122, 75, 39, .08);
      overflow: hidden;
    }}
    .mobile-day-card.is-today {{
      border-color: var(--mint);
      box-shadow: 0 12px 30px rgba(71, 185, 169, .18);
    }}
    .mobile-day-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 12px 14px;
      background: linear-gradient(90deg, #fff0bf, #e7f8f4);
      color: var(--caramel);
      font-weight: 900;
    }}
    .mobile-day-head span:first-child {{
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .mobile-day-count {{
      min-width: 32px;
      height: 28px;
      display: inline-grid;
      place-items: center;
      border-radius: 999px;
      background: #fffdf5;
      color: #167c70;
      font-size: 13px;
    }}
    .mobile-events {{
      display: grid;
      gap: 8px;
      padding: 10px;
    }}
    .mobile-event {{
      width: 100%;
      min-height: 58px;
      border: 0;
      border-left: 5px solid var(--mint);
      border-radius: 8px;
      padding: 10px 12px;
      background: var(--mint-soft);
      color: var(--cocoa);
      text-align: left;
    }}
    .mobile-event.product {{ border-left-color: var(--caramel); background: #fff0bf; }}
    .mobile-event.event {{ border-left-color: var(--sky); background: #eaf5ff; }}
    .mobile-event.campaign {{ border-left-color: var(--berry); background: #ffeaf0; }}
    .mobile-event.reservation {{ border-left-color: var(--leaf); background: #ecf8e9; }}
    .mobile-event strong {{
      display: block;
      font-size: 14px;
      line-height: 1.35;
      letter-spacing: 0;
    }}
    .mobile-event span {{
      display: block;
      margin-top: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }}
    dialog {{
      width: min(720px, calc(100vw - 28px));
      border: 1px solid rgba(122, 75, 39, .16);
      border-radius: 8px;
      padding: 0;
      box-shadow: var(--shadow);
    }}
    dialog::backdrop {{ background: rgba(53, 36, 23, .34); }}
    .modal-body {{ padding: 18px; }}
    .modal-body h2 {{ margin: 0 0 10px; font-size: 22px; letter-spacing: 0; }}
    .modal-actions {{
      display: flex;
      justify-content: flex-end;
      padding: 12px 18px;
      border-top: 1px solid rgba(122, 75, 39, .12);
      background: #fff8e6;
    }}
    @media (max-width: 980px) {{
      .topbar-inner, .layout {{ padding-left: 12px; padding-right: 12px; }}
      .topbar-inner, .layout, .toolbar {{ grid-template-columns: 1fr; }}
      .month-controls {{ justify-content: start; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .side-panel {{ position: static; max-height: none; }}
      .day {{ min-height: 112px; padding: 6px; }}
    }}
    @media (max-width: 640px) {{
      .brand {{ grid-template-columns: 52px minmax(0, 1fr); }}
      .pudding-mark {{ width: 52px; height: 52px; }}
      .topbar-inner {{ gap: 12px; }}
      .brand h1 {{ font-size: 20px; }}
      .brand p {{ font-size: 12px; }}
      .month-controls {{
        display: grid;
        grid-template-columns: 44px 1fr 44px;
        width: 100%;
      }}
      .icon-button, .text-button {{
        width: 100%;
        min-height: 46px;
      }}
      .layout {{
        padding: 14px 10px 28px;
        gap: 12px;
      }}
      .toolbar {{
        padding: 10px;
        gap: 8px;
      }}
      .toolbar .field:first-child {{
        order: -1;
      }}
      .field {{
        min-height: 48px;
      }}
      .field span {{
        min-width: 34px;
      }}
      .stats {{ grid-template-columns: 1fr; }}
      .stat {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 52px;
      }}
      .stat span {{
        margin-top: 0;
      }}
      .calendar-panel {{
        display: none;
      }}
      .mobile-schedule {{
        display: grid;
        gap: 12px;
      }}
      .side-panel {{
        display: none;
      }}
    }}
  </style>
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <svg class="pudding-mark" viewBox="0 0 96 96" role="img" aria-label="pudding calendar mark">
            <path d="M20 38c0-17 12-28 28-28s28 11 28 28v24c0 13-12 24-28 24S20 75 20 62V38Z" fill="#FFE08A"/>
            <path d="M24 35c3-13 12-20 24-20s21 7 24 20c-6 5-12 5-18 1-5-3-8-3-13 0-6 4-11 4-17-1Z" fill="#7A4B27"/>
            <circle cx="38" cy="51" r="3.5" fill="#352417"/>
            <circle cx="58" cy="51" r="3.5" fill="#352417"/>
            <path d="M42 63c4 4 8 4 12 0" fill="none" stroke="#352417" stroke-width="3" stroke-linecap="round"/>
            <path d="M28 79h40" stroke="#47B9A9" stroke-width="5" stroke-linecap="round"/>
          </svg>
          <div>
            <h1>ポムポムプリン予定帳</h1>
            <p>{escape(generated_at)} / {escape(window_text)}</p>
          </div>
        </div>
        <div class="month-controls" aria-label="月移動">
          <button class="icon-button" id="prevMonth" title="前の月" aria-label="前の月">‹</button>
          <button class="text-button" id="todayButton">今日</button>
          <button class="icon-button" id="nextMonth" title="次の月" aria-label="次の月">›</button>
        </div>
      </div>
    </header>
    <main class="layout">
      <section class="toolbar" aria-label="絞り込み">
        <label class="field"><span>検索</span><input id="searchInput" type="search" placeholder="タイトル、会場、ソース"></label>
        <label class="field"><span>種別</span><select id="kindFilter"><option value="all">すべて</option></select></label>
        <label class="field"><span>状態</span><select id="statusFilter"><option value="all">すべて</option></select></label>
        <button class="text-button" id="resetButton">リセット</button>
      </section>
      <section class="stats" aria-label="集計">
        <div class="stat"><strong id="statTotal">0</strong><span>表示中</span></div>
        <div class="stat"><strong id="statReview">0</strong><span>確認待ち</span></div>
        <div class="stat"><strong id="statConfirmed">0</strong><span>確認済み</span></div>
        <div class="stat"><strong id="statUndated">0</strong><span>日付未確定</span></div>
      </section>
      <section class="calendar-panel" aria-label="月間カレンダー">
        <div class="calendar-head" id="calendarTitle"></div>
        <div class="calendar-grid" id="calendarGrid"></div>
      </section>
      <section class="mobile-schedule" id="mobileSchedule" aria-label="スマホ用予定一覧"></section>
      <aside class="side-panel" aria-label="詳細一覧">
        <div class="side-header">
          <h2 id="agendaTitle">これからの予定</h2>
          <p id="agendaSubtitle">気になる予定をチェック</p>
        </div>
        <div class="agenda" id="agenda"></div>
      </aside>
    </main>
  </div>
  <dialog id="detailDialog">
    <div class="modal-body" id="modalBody"></div>
    <div class="modal-actions"><button class="text-button" id="closeDialog">閉じる</button></div>
  </dialog>
  <script>
    const ITEMS = {data_json};
    const state = {{
      current: initialMonth(ITEMS),
      query: "",
      kind: "all",
      status: "all",
      selectedDate: ""
    }};
    const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
    const kindLabels = {json.dumps(KIND_LABELS, ensure_ascii=False)};
    const statusLabels = {json.dumps(STATUS_LABELS, ensure_ascii=False)};

    const grid = document.getElementById("calendarGrid");
    const title = document.getElementById("calendarTitle");
    const agenda = document.getElementById("agenda");
    const mobileSchedule = document.getElementById("mobileSchedule");
    const agendaTitle = document.getElementById("agendaTitle");
    const agendaSubtitle = document.getElementById("agendaSubtitle");
    const detailDialog = document.getElementById("detailDialog");
    const modalBody = document.getElementById("modalBody");

    document.getElementById("prevMonth").addEventListener("click", () => shiftMonth(-1));
    document.getElementById("nextMonth").addEventListener("click", () => shiftMonth(1));
    document.getElementById("todayButton").addEventListener("click", () => {{
      state.current = startOfMonth(new Date());
      state.selectedDate = isoDate(new Date());
      render();
    }});
    document.getElementById("resetButton").addEventListener("click", () => {{
      state.query = "";
      state.kind = "all";
      state.status = "all";
      state.selectedDate = "";
      document.getElementById("searchInput").value = "";
      document.getElementById("kindFilter").value = "all";
      document.getElementById("statusFilter").value = "all";
      render();
    }});
    document.getElementById("searchInput").addEventListener("input", event => {{
      state.query = event.target.value.trim().toLowerCase();
      render();
    }});
    document.getElementById("kindFilter").addEventListener("change", event => {{
      state.kind = event.target.value;
      render();
    }});
    document.getElementById("statusFilter").addEventListener("change", event => {{
      state.status = event.target.value;
      render();
    }});
    document.getElementById("closeDialog").addEventListener("click", () => detailDialog.close());

    fillFilters();
    render();

    function initialMonth(items) {{ return startOfMonth(new Date()); }}
    function startOfMonth(date) {{ return new Date(date.getFullYear(), date.getMonth(), 1); }}
    function isoDate(date) {{
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, "0");
      const d = String(date.getDate()).padStart(2, "0");
      return `${{y}}-${{m}}-${{d}}`;
    }}
    function parseLocalDate(value) {{
      const [y, m, d] = value.split("-").map(Number);
      return new Date(y, m - 1, d);
    }}
    function shiftMonth(delta) {{
      state.current = new Date(state.current.getFullYear(), state.current.getMonth() + delta, 1);
      state.selectedDate = "";
      render();
    }}
    function fillFilters() {{
      const kindFilter = document.getElementById("kindFilter");
      const statusFilter = document.getElementById("statusFilter");
      Object.entries(kindLabels).forEach(([value, label]) => kindFilter.append(new Option(label, value)));
      Object.entries(statusLabels).forEach(([value, label]) => statusFilter.append(new Option(label, value)));
    }}
    function filteredItems() {{
      return ITEMS.filter(item => {{
        const text = [item.title, item.sellerOrVenue, item.sourceName, item.reviewReason, item.notes].join(" ").toLowerCase();
        return (state.kind === "all" || item.kind === state.kind)
          && (state.status === "all" || item.status === state.status)
          && (!state.query || text.includes(state.query));
      }});
    }}
    function render() {{
      const items = filteredItems();
      renderStats(items);
      renderCalendar(items);
      renderAgenda(items);
      renderMobileSchedule(items);
    }}
    function renderStats(items) {{
      document.getElementById("statTotal").textContent = items.length;
      document.getElementById("statReview").textContent = items.filter(item => item.status === "needs_review").length;
      document.getElementById("statConfirmed").textContent = items.filter(item => item.status === "confirmed").length;
      document.getElementById("statUndated").textContent = items.filter(item => !item.primaryDate).length;
    }}
    function renderCalendar(items) {{
      title.innerHTML = "";
      weekdays.forEach(day => {{
        const el = document.createElement("div");
        el.className = "weekday";
        el.textContent = day;
        title.append(el);
      }});
      grid.innerHTML = "";
      const year = state.current.getFullYear();
      const month = state.current.getMonth();
      const first = new Date(year, month, 1);
      const start = new Date(year, month, 1 - first.getDay());
      const today = isoDate(new Date());
      for (let index = 0; index < 42; index += 1) {{
        const day = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index);
        const dayIso = isoDate(day);
        const dayItems = items.filter(item => item.primaryDate === dayIso);
        const cell = document.createElement("div");
        cell.className = "day";
        if (day.getMonth() !== month) cell.classList.add("is-muted");
        if (dayIso === today) cell.classList.add("is-today");
        const dayNumber = document.createElement("div");
        dayNumber.className = "day-number";
        dayNumber.innerHTML = `<span>${{day.getDate()}}</span>${{dayItems.length ? `<span class="day-count">${{dayItems.length}}</span>` : ""}}`;
        cell.append(dayNumber);
        const list = document.createElement("div");
        list.className = "event-list";
        dayItems.slice(0, 3).forEach(item => list.append(eventButton(item)));
        if (dayItems.length > 3) {{
          const more = document.createElement("button");
          more.className = "more-button";
          more.textContent = `+${{dayItems.length - 3}}件`;
          more.addEventListener("click", () => {{
            state.selectedDate = dayIso;
            renderAgenda(items);
          }});
          list.append(more);
        }}
        cell.append(list);
        cell.addEventListener("click", event => {{
          if (event.target.closest("button")) return;
          state.selectedDate = dayIso;
          renderAgenda(items);
        }});
        grid.append(cell);
      }}
      const monthLabel = `${{year}}年${{month + 1}}月`;
      document.querySelector(".brand h1").textContent = `ポムポムプリン予定帳 / ${{monthLabel}}`;
    }}
    function eventButton(item) {{
      const button = document.createElement("button");
      button.className = `event-pill ${{item.kind}}`;
      button.innerHTML = `<strong>${{escapeHtml(item.title)}}</strong><span>${{escapeHtml(item.kindLabel)}} / ${{escapeHtml(item.statusLabel)}}</span>`;
      button.addEventListener("click", () => openDetail(item));
      return button;
    }}
    function renderAgenda(items) {{
      agenda.innerHTML = "";
      const scoped = state.selectedDate ? items.filter(item => item.primaryDate === state.selectedDate) : items;
      const dated = scoped.filter(item => item.primaryDate).sort((a, b) => a.primaryDate.localeCompare(b.primaryDate));
      const undated = scoped.filter(item => !item.primaryDate);
      const ordered = [...dated, ...undated].slice(0, 80);
      agendaTitle.textContent = state.selectedDate ? `${{state.selectedDate}} の予定` : "これからの予定";
      agendaSubtitle.textContent = state.selectedDate ? `${{ordered.length}}件` : "日付が近い順";
      if (!ordered.length) {{
        agenda.innerHTML = `<div class="empty">表示できる候補がありません</div>`;
        return;
      }}
      ordered.forEach(item => agenda.append(agendaItem(item)));
    }}
    function renderMobileSchedule(items) {{
      mobileSchedule.innerHTML = "";
      const dated = items.filter(item => item.primaryDate).sort((a, b) => a.primaryDate.localeCompare(b.primaryDate));
      const undated = items.filter(item => !item.primaryDate);
      const grouped = groupByDate(dated);
      const today = isoDate(new Date());
      Object.entries(grouped).forEach(([date, dateItems]) => {{
        mobileSchedule.append(mobileDayCard(date, dateItems, date === today));
      }});
      if (undated.length) {{
        mobileSchedule.append(mobileDayCard("日付未確定", undated, false));
      }}
      if (!mobileSchedule.children.length) {{
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "表示できる予定がありません";
        mobileSchedule.append(empty);
      }}
    }}
    function groupByDate(items) {{
      return items.reduce((groups, item) => {{
        const key = item.primaryDate || "日付未確定";
        if (!groups[key]) groups[key] = [];
        groups[key].push(item);
        return groups;
      }}, {{}});
    }}
    function mobileDayCard(date, items, isToday) {{
      const card = document.createElement("article");
      card.className = `mobile-day-card${{isToday ? " is-today" : ""}}`;
      const head = document.createElement("div");
      head.className = "mobile-day-head";
      head.innerHTML = `<span>${{escapeHtml(formatMobileDate(date, isToday))}}</span><span class="mobile-day-count">${{items.length}}</span>`;
      card.append(head);
      const list = document.createElement("div");
      list.className = "mobile-events";
      items.forEach(item => list.append(mobileEventButton(item)));
      card.append(list);
      return card;
    }}
    function mobileEventButton(item) {{
      const button = document.createElement("button");
      button.className = `mobile-event ${{item.kind}}`;
      button.innerHTML = `<strong>${{escapeHtml(item.title)}}</strong><span>${{escapeHtml(dateSummary(item))}} / ${{escapeHtml(item.kindLabel)}}</span>`;
      button.addEventListener("click", () => openDetail(item));
      return button;
    }}
    function formatMobileDate(value, isToday) {{
      if (value === "日付未確定") return value;
      const date = parseLocalDate(value);
      const label = `${{date.getMonth() + 1}}/${{date.getDate()}}（${{weekdays[date.getDay()]}}）`;
      return isToday ? `${{label}} 今日` : label;
    }}
    function agendaItem(item) {{
      const el = document.createElement("article");
      el.className = "agenda-item";
      el.innerHTML = `
        <h3>${{escapeHtml(item.title)}}</h3>
        <div class="meta">
          <span class="tag">${{escapeHtml(item.kindLabel)}}</span>
          <span class="tag ${{item.status === "needs_review" ? "review" : item.status}}">${{escapeHtml(item.statusLabel)}}</span>
        </div>
        <p class="detail-text">${{escapeHtml(dateSummary(item))}}</p>
        <p class="detail-text">${{escapeHtml(item.sellerOrVenue || item.sourceName || "")}}</p>
      `;
      el.addEventListener("click", () => openDetail(item));
      return el;
    }}
    function openDetail(item) {{
      modalBody.innerHTML = `
        <h2>${{escapeHtml(item.title)}}</h2>
        <div class="meta">
          <span class="tag">${{escapeHtml(item.kindLabel)}}</span>
          <span class="tag ${{item.status === "needs_review" ? "review" : item.status}}">${{escapeHtml(item.statusLabel)}}</span>
        </div>
        <p class="detail-text">${{escapeHtml(dateSummary(item))}}</p>
        <p class="detail-text">${{escapeHtml(item.sellerOrVenue || "")}}</p>
        <p class="detail-text">${{escapeHtml(item.reviewReason || "")}}</p>
        <p class="detail-text">${{escapeHtml(item.notes || "")}}</p>
        ${{sourceLinks(item.sourceUrl)}}
      `;
      detailDialog.showModal();
    }}
    function dateSummary(item) {{
      const rows = [];
      if (item.releaseDate) rows.push(`発売日: ${{item.releaseDate}}`);
      if (item.startDate || item.endDate) rows.push(`期間: ${{item.startDate || "未定"}} - ${{item.endDate || "未定"}}`);
      if (item.reservationStart) rows.push(`予約開始: ${{item.reservationStart}}`);
      return rows.join(" / ") || "日付未確定";
    }}
    function sourceLinks(value) {{
      if (!value) return "";
      return value.split(" | ").map(url => `<a class="source-link" href="${{escapeAttr(url)}}" target="_blank" rel="noreferrer">ソースを開く</a>`).join("<br>");
    }}
    function escapeHtml(value) {{
      return String(value || "").replace(/[&<>"']/g, char => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[char]));
    }}
    function escapeAttr(value) {{ return escapeHtml(value).replace(/`/g, "&#96;"); }}
  </script>
</body>
</html>
"""
