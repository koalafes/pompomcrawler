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
        "imageUrl": item.image_url,
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
      grid-template-columns: minmax(0, 1fr);
      align-items: center;
      min-width: 0;
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
      grid-template-columns: minmax(170px, 240px);
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
      display: none;
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
    .mobile-outlook {{
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
    .agenda-item.has-image {{
      display: grid;
      grid-template-columns: 82px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }}
    .agenda-item:last-child {{ border-bottom: 0; }}
    .event-image {{
      display: block;
      overflow: hidden;
      border-radius: 8px;
      background: #fff0bf;
      border: 1px solid rgba(122, 75, 39, .12);
      box-shadow: 0 8px 18px rgba(122, 75, 39, .08);
    }}
    .event-image img {{
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    .agenda-thumb {{
      width: 82px;
      aspect-ratio: 1;
    }}
    .agenda-content {{
      min-width: 0;
    }}
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
    .mobile-outlook-panel {{
      border-radius: 8px;
      background: rgba(255, 253, 245, .92);
      box-shadow: 0 10px 24px rgba(122, 75, 39, .08);
      overflow: hidden;
      border: 1px solid rgba(122, 75, 39, .13);
    }}
    .mobile-weekdays {{
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      background: linear-gradient(90deg, #fff0bf, #e7f8f4);
      border-bottom: 1px solid rgba(122, 75, 39, .12);
    }}
    .mobile-weekdays span {{
      min-height: 30px;
      display: grid;
      place-items: center;
      color: var(--caramel);
      font-size: 11px;
      font-weight: 900;
    }}
    .mobile-grid {{
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
    }}
    .mobile-day {{
      min-height: 54px;
      padding: 5px 3px;
      border: 0;
      border-right: 1px solid rgba(122, 75, 39, .09);
      border-bottom: 1px solid rgba(122, 75, 39, .09);
      background: rgba(255, 255, 250, .92);
      color: var(--cocoa);
      text-align: center;
      cursor: pointer;
    }}
    .mobile-day:nth-child(7n) {{ border-right: 0; }}
    .mobile-day.is-muted {{
      background: rgba(255, 248, 228, .52);
      color: #a68b75;
    }}
    .mobile-day.is-today {{
      background: linear-gradient(180deg, #fff2b7, #e7f9f4);
      box-shadow: inset 0 0 0 2px var(--mint);
    }}
    .mobile-day.is-selected {{
      background: #fff0bf;
      box-shadow: inset 0 0 0 2px var(--caramel);
    }}
    .mobile-day-number {{
      display: inline-grid;
      place-items: center;
      width: 24px;
      height: 24px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 900;
    }}
    .mobile-day.is-today .mobile-day-number {{
      background: var(--caramel);
      color: #fff;
    }}
    .mobile-day-dots {{
      height: 12px;
      margin-top: 3px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 3px;
    }}
    .mobile-dot {{
      width: 6px;
      height: 6px;
      border-radius: 999px;
      background: var(--mint);
    }}
    .mobile-dot.product {{ background: var(--caramel); }}
    .mobile-dot.event {{ background: var(--sky); }}
    .mobile-dot.campaign {{ background: var(--berry); }}
    .mobile-dot.reservation {{ background: var(--leaf); }}
    .mobile-day-more {{
      min-width: 14px;
      height: 14px;
      display: inline-grid;
      place-items: center;
      border-radius: 999px;
      background: var(--caramel);
      color: #fff;
      font-size: 9px;
      font-weight: 900;
    }}
    .mobile-selected {{
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }}
    .mobile-selected-head {{
      color: var(--caramel);
      font-size: 15px;
      font-weight: 900;
      padding: 0 2px;
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
    .mobile-event.has-image {{
      display: grid;
      grid-template-columns: 74px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      padding: 8px 10px;
    }}
    .mobile-thumb {{
      width: 74px;
      aspect-ratio: 1;
    }}
    .mobile-event-content {{
      min-width: 0;
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
    .modal-image {{
      width: 100%;
      aspect-ratio: 16 / 9;
      margin-bottom: 14px;
    }}
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
      .field {{
        min-height: 48px;
      }}
      .field span {{
        min-width: 34px;
      }}
      .stats {{ display: none; }}
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
      .mobile-outlook {{
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
        <label class="field"><span>種別</span><select id="kindFilter"><option value="all">すべて</option></select></label>
      </section>
      <section class="calendar-panel" aria-label="月間カレンダー">
        <div class="calendar-head" id="calendarTitle"></div>
        <div class="calendar-grid" id="calendarGrid"></div>
      </section>
      <section class="mobile-outlook" id="mobileOutlook" aria-label="スマホ用予定カレンダー">
        <div class="mobile-outlook-panel">
          <div class="mobile-weekdays" id="mobileWeekdays"></div>
          <div class="mobile-grid" id="mobileGrid"></div>
        </div>
        <div class="mobile-selected" id="mobileSelected"></div>
      </section>
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
      kind: "all",
      selectedDate: ""
    }};
    const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
    const kindLabels = {json.dumps(KIND_LABELS, ensure_ascii=False)};

    const grid = document.getElementById("calendarGrid");
    const title = document.getElementById("calendarTitle");
    const agenda = document.getElementById("agenda");
    const mobileWeekdays = document.getElementById("mobileWeekdays");
    const mobileGrid = document.getElementById("mobileGrid");
    const mobileSelected = document.getElementById("mobileSelected");
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
    document.getElementById("kindFilter").addEventListener("change", event => {{
      state.kind = event.target.value;
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
      Object.entries(kindLabels).forEach(([value, label]) => kindFilter.append(new Option(label, value)));
    }}
    function filteredItems() {{
      return ITEMS.filter(item => {{
        return item.status !== "excluded" && (state.kind === "all" || item.kind === state.kind);
      }});
    }}
    function render() {{
      const items = filteredItems();
      renderStats(items);
      renderCalendar(items);
      renderAgenda(items);
      renderMobileOutlook(items);
    }}
    function renderStats(items) {{
      return;
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
      button.innerHTML = `<strong>${{escapeHtml(item.title)}}</strong><span>${{escapeHtml(item.kindLabel)}} / ${{escapeHtml(dateSummary(item))}}</span>`;
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
    function renderMobileOutlook(items) {{
      mobileWeekdays.innerHTML = "";
      weekdays.forEach(day => {{
        const el = document.createElement("span");
        el.textContent = day;
        mobileWeekdays.append(el);
      }});
      mobileGrid.innerHTML = "";
      const grouped = groupByDate(items.filter(item => item.primaryDate));
      const today = isoDate(new Date());
      const year = state.current.getFullYear();
      const month = state.current.getMonth();
      const first = new Date(year, month, 1);
      const start = new Date(year, month, 1 - first.getDay());
      const visibleStart = isoDate(start);
      const visibleEnd = isoDate(new Date(start.getFullYear(), start.getMonth(), start.getDate() + 41));
      if (!state.selectedDate || state.selectedDate < visibleStart || state.selectedDate > visibleEnd) {{
        state.selectedDate = year === new Date().getFullYear() && month === new Date().getMonth()
          ? today
          : isoDate(new Date(year, month, 1));
      }}
      for (let index = 0; index < 42; index += 1) {{
        const day = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index);
        const dayIso = isoDate(day);
        const dayItems = grouped[dayIso] || [];
        mobileGrid.append(mobileDayButton(day, dayIso, dayItems, day.getMonth() !== month, dayIso === today));
      }}
      renderMobileSelected(items);
    }}
    function groupByDate(items) {{
      return items.reduce((groups, item) => {{
        const key = item.primaryDate || "日付未確定";
        if (!groups[key]) groups[key] = [];
        groups[key].push(item);
        return groups;
      }}, {{}});
    }}
    function mobileDayButton(day, dayIso, items, isMuted, isToday) {{
      const button = document.createElement("button");
      button.className = "mobile-day";
      if (isMuted) button.classList.add("is-muted");
      if (isToday) button.classList.add("is-today");
      if (state.selectedDate === dayIso) button.classList.add("is-selected");
      button.innerHTML = `<span class="mobile-day-number">${{day.getDate()}}</span>${{mobileDots(items)}}`;
      button.addEventListener("click", () => {{
        state.selectedDate = dayIso;
        render();
      }});
      return button;
    }}
    function mobileDots(items) {{
      if (!items.length) return `<span class="mobile-day-dots"></span>`;
      const dots = items.slice(0, 3).map(item => `<span class="mobile-dot ${{escapeAttr(item.kind)}}"></span>`).join("");
      const more = items.length > 3 ? `<span class="mobile-day-more">+${{items.length - 3}}</span>` : "";
      return `<span class="mobile-day-dots">${{dots}}${{more}}</span>`;
    }}
    function renderMobileSelected(items) {{
      mobileSelected.innerHTML = "";
      const selectedItems = items.filter(item => item.primaryDate === state.selectedDate);
      const title = document.createElement("div");
      title.className = "mobile-selected-head";
      title.textContent = formatMobileDate(state.selectedDate, state.selectedDate === isoDate(new Date()));
      mobileSelected.append(title);
      if (!selectedItems.length) {{
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "この日の予定はまだありません";
        mobileSelected.append(empty);
        return;
      }}
      selectedItems.forEach(item => mobileSelected.append(mobileEventButton(item)));
    }}
    function mobileEventButton(item) {{
      const button = document.createElement("button");
      button.className = `mobile-event ${{item.kind}}`;
      if (item.imageUrl) button.classList.add("has-image");
      button.innerHTML = `
        ${{imageMarkup(item, "event-image mobile-thumb")}}
        <div class="mobile-event-content">
          <strong>${{escapeHtml(item.title)}}</strong>
          <span>${{escapeHtml(dateSummary(item))}} / ${{escapeHtml(item.kindLabel)}}</span>
        </div>
      `;
      button.addEventListener("click", () => openDetail(item));
      return button;
    }}
    function formatMobileDate(value, isToday) {{
      if (!value) return "日付未確定";
      const date = parseLocalDate(value);
      const label = `${{date.getMonth() + 1}}/${{date.getDate()}}（${{weekdays[date.getDay()]}}）`;
      return isToday ? `${{label}} 今日` : label;
    }}
    function agendaItem(item) {{
      const el = document.createElement("article");
      el.className = item.imageUrl ? "agenda-item has-image" : "agenda-item";
      el.innerHTML = `
        ${{imageMarkup(item, "event-image agenda-thumb")}}
        <div class="agenda-content">
          <h3>${{escapeHtml(item.title)}}</h3>
          <div class="meta">
            <span class="tag">${{escapeHtml(item.kindLabel)}}</span>
          </div>
          <p class="detail-text">${{escapeHtml(dateSummary(item))}}</p>
          <p class="detail-text">${{escapeHtml(item.sellerOrVenue || item.sourceName || "")}}</p>
        </div>
      `;
      el.addEventListener("click", () => openDetail(item));
      return el;
    }}
    function openDetail(item) {{
      modalBody.innerHTML = `
        ${{imageMarkup(item, "event-image modal-image")}}
        <h2>${{escapeHtml(item.title)}}</h2>
        <div class="meta">
          <span class="tag">${{escapeHtml(item.kindLabel)}}</span>
        </div>
        <p class="detail-text">${{escapeHtml(dateSummary(item))}}</p>
        <p class="detail-text">${{escapeHtml(item.sellerOrVenue || "")}}</p>
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
    function imageMarkup(item, className) {{
      const imageUrl = safeImageUrl(item.imageUrl);
      if (!imageUrl) return "";
      return `<span class="${{escapeAttr(className)}}"><img src="${{imageUrl}}" alt="${{escapeAttr(item.title)}}" loading="lazy" referrerpolicy="no-referrer"></span>`;
    }}
    function safeImageUrl(value) {{
      try {{
        const url = new URL(String(value || ""), window.location.href);
        return ["http:", "https:"].includes(url.protocol) ? escapeAttr(url.href) : "";
      }} catch {{
        return "";
      }}
    }}
    function escapeHtml(value) {{
      return String(value || "").replace(/[&<>"']/g, char => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[char]));
    }}
    function escapeAttr(value) {{ return escapeHtml(value).replace(/`/g, "&#96;"); }}
  </script>
</body>
</html>
"""
