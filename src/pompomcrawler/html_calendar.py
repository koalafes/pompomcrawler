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
  <title>ポムポムプリン収集カレンダー</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f5ef;
      --surface: #ffffff;
      --ink: #25211c;
      --muted: #6d665d;
      --line: #ded8ce;
      --accent: #0f766e;
      --accent-soft: #d7efec;
      --gold: #e0a92f;
      --rose: #cf5b73;
      --blue: #3b6ea8;
      --green: #3d8b5b;
      --shadow: 0 16px 40px rgba(37, 33, 28, .08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
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
      background: rgba(247, 245, 239, .92);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(16px);
    }}
    .topbar-inner {{
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 14px 20px;
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 16px;
      align-items: center;
    }}
    .brand h1 {{
      margin: 0;
      font-size: clamp(20px, 2.2vw, 30px);
      letter-spacing: 0;
      line-height: 1.15;
    }}
    .brand p {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .month-controls {{
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
    }}
    .icon-button, .text-button {{
      min-height: 40px;
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--ink);
      cursor: pointer;
      box-shadow: 0 1px 0 rgba(37, 33, 28, .04);
    }}
    .icon-button {{
      width: 40px;
      display: inline-grid;
      place-items: center;
      border-radius: 8px;
      font-size: 20px;
      line-height: 1;
    }}
    .text-button {{
      border-radius: 8px;
      padding: 0 14px;
      font-weight: 700;
    }}
    .icon-button:hover, .text-button:hover {{ border-color: var(--accent); }}
    .layout {{
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 18px 20px 32px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 18px;
      align-items: start;
    }}
    .toolbar {{
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: minmax(220px, 1fr) repeat(2, minmax(150px, 190px)) auto;
      gap: 10px;
      align-items: center;
    }}
    .field {{
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 42px;
      padding: 0 12px;
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
    }}
    .field span {{ color: var(--muted); }}
    .field input, .field select {{
      width: 100%;
      min-width: 0;
      border: 0;
      outline: 0;
      background: transparent;
      color: var(--ink);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      grid-column: 1 / -1;
    }}
    .stat {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-width: 0;
    }}
    .stat strong {{ display: block; font-size: 24px; line-height: 1; }}
    .stat span {{ display: block; margin-top: 4px; color: var(--muted); font-size: 12px; }}
    .calendar-panel, .side-panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .calendar-head {{
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      border-bottom: 1px solid var(--line);
      background: #f2eee5;
    }}
    .weekday {{
      padding: 10px 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-align: center;
    }}
    .calendar-grid {{
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
    }}
    .day {{
      min-height: 132px;
      padding: 8px;
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      background: #fffdfa;
      overflow: hidden;
    }}
    .day:nth-child(7n) {{ border-right: 0; }}
    .day.is-muted {{ background: #f6f3ed; color: #8b8479; }}
    .day.is-today {{
      background: #eef8f6;
      box-shadow: inset 0 0 0 3px var(--accent);
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
      background: var(--accent);
      color: #fff;
      box-shadow: 0 4px 12px rgba(15, 118, 110, .24);
    }}
    .day-count {{
      min-width: 22px;
      height: 22px;
      display: inline-grid;
      place-items: center;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
    }}
    .event-list {{
      display: grid;
      gap: 5px;
    }}
    .event-pill {{
      display: block;
      width: 100%;
      min-height: 32px;
      padding: 5px 7px;
      border: 0;
      border-left: 4px solid var(--accent);
      border-radius: 6px;
      background: #eef8f6;
      color: var(--ink);
      text-align: left;
      cursor: pointer;
      overflow: hidden;
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
    .event-pill.product {{ border-left-color: var(--gold); background: #fff5d8; }}
    .event-pill.event {{ border-left-color: var(--blue); background: #eaf2fb; }}
    .event-pill.campaign {{ border-left-color: var(--rose); background: #fdebf0; }}
    .event-pill.reservation {{ border-left-color: var(--green); background: #eaf7ef; }}
    .more-button {{
      width: 100%;
      border: 0;
      background: transparent;
      color: var(--accent);
      cursor: pointer;
      font-weight: 800;
      font-size: 12px;
      text-align: left;
      padding: 2px 0;
    }}
    .side-panel {{
      position: sticky;
      top: 92px;
      max-height: calc(100vh - 112px);
      display: flex;
      flex-direction: column;
    }}
    .side-header {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: #f2eee5;
    }}
    .side-header h2 {{ margin: 0; font-size: 18px; letter-spacing: 0; }}
    .side-header p {{ margin: 4px 0 0; color: var(--muted); font-size: 12px; }}
    .agenda {{
      padding: 12px;
      overflow: auto;
      display: grid;
      gap: 10px;
    }}
    .agenda-item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fffdfa;
    }}
    .agenda-item h3 {{
      margin: 0;
      font-size: 15px;
      line-height: 1.35;
      letter-spacing: 0;
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
      background: #ece7dc;
      color: var(--ink);
      font-size: 12px;
      font-weight: 700;
    }}
    .tag.review {{ background: #fff0cc; }}
    .tag.confirmed {{ background: #dff4e7; }}
    .tag.excluded {{ background: #ececec; color: #777; }}
    .detail-text {{ margin: 0; color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }}
    .source-link {{
      display: inline-block;
      margin-top: 10px;
      color: var(--accent);
      font-weight: 800;
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .empty {{
      padding: 28px 14px;
      color: var(--muted);
      text-align: center;
    }}
    dialog {{
      width: min(720px, calc(100vw - 28px));
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0;
      box-shadow: var(--shadow);
    }}
    dialog::backdrop {{ background: rgba(37, 33, 28, .34); }}
    .modal-body {{ padding: 18px; }}
    .modal-body h2 {{ margin: 0 0 10px; font-size: 22px; letter-spacing: 0; }}
    .modal-actions {{
      display: flex;
      justify-content: flex-end;
      padding: 12px 18px;
      border-top: 1px solid var(--line);
      background: #f7f5ef;
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
      .calendar-panel {{ overflow-x: auto; }}
      .calendar-head, .calendar-grid {{ min-width: 760px; }}
      .stats {{ grid-template-columns: 1fr; }}
      .toolbar {{ gap: 8px; }}
    }}
  </style>
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <h1>ポムポムプリン収集カレンダー</h1>
          <p>{escape(generated_at)} 生成 / 対象: {escape(window_text)} / 確認待ちを優先して整理</p>
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
      <aside class="side-panel" aria-label="詳細一覧">
        <div class="side-header">
          <h2 id="agendaTitle">一覧</h2>
          <p id="agendaSubtitle">日付が近い順</p>
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
      document.querySelector(".brand h1").textContent = `ポムポムプリン収集カレンダー / ${{monthLabel}}`;
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
      agendaTitle.textContent = state.selectedDate ? `${{state.selectedDate}} の候補` : "候補一覧";
      agendaSubtitle.textContent = state.selectedDate ? `${{ordered.length}}件` : "日付が近い順 / 未日付は末尾";
      if (!ordered.length) {{
        agenda.innerHTML = `<div class="empty">表示できる候補がありません</div>`;
        return;
      }}
      ordered.forEach(item => agenda.append(agendaItem(item)));
    }}
    function agendaItem(item) {{
      const el = document.createElement("article");
      el.className = "agenda-item";
      el.innerHTML = `
        <h3>${{escapeHtml(item.title)}}</h3>
        <div class="meta">
          <span class="tag">${{escapeHtml(item.kindLabel)}}</span>
          <span class="tag ${{item.status === "needs_review" ? "review" : item.status}}">${{escapeHtml(item.statusLabel)}}</span>
          <span class="tag">信頼度 ${{Math.round(item.confidence * 100)}}%</span>
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
          <span class="tag">信頼度 ${{Math.round(item.confidence * 100)}}%</span>
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
