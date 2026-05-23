# pompomcrawler

ポムポムプリンの新商品・イベント情報を広めに集め、確認しやすい CSV/XLSX のスケジュール表にするための CLI です。

外部検索 API や SNS API は不要です。OpenAI API キーがある場合は、取得済みページ本文から商品名・日付・場所などを構造化抽出します。キーがない場合も、固定巡回、確認チェックリスト生成、手動 CSV 取り込み、CSV 出力は動きます。

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
```

`.env` に `OPENAI_API_KEY` を設定すると、`extract` で OpenAI API による抽出が使われます。

## Commands

```bash
pompomcrawler crawl
pompomcrawler make-checklist
pompomcrawler import-manual samples/manual_items.csv
pompomcrawler extract
pompomcrawler export
pompomcrawler export-html
```

`export` と `export-html` は、予定作成で使いやすいようにデフォルトで「直近30日＋未来」の日付付き候補だけに絞ります。日付未確定の候補は確認漏れ防止のため残します。過去分をすべて出したい場合は `--all-history` を使ってください。

開発中にパッケージをインストールせずに動かす場合:

```bash
PYTHONPATH=src python -m pompomcrawler.cli crawl
```

API消費を抑えて試す場合:

```bash
pompomcrawler extract --limit 5
pompomcrawler extract --last 68
pompomcrawler extract --no-openai
pompomcrawler extract --no-openai --replace
```

## Workflow

1. `crawl` でサンリオ公式、PR/ニュース媒体、公開ページを巡回します。
2. `make-checklist` で Google/X/Instagram/TikTok などの確認リンクを作ります。
3. SNS や検索で見つけた URL は `import-manual` で投入します。
4. `extract` で本文から候補行を作ります。
5. `export` で `outputs/pompompurin_schedule.csv`、`outputs/pompompurin_schedule.xlsx`、`outputs/pompompurin_calendar.html` を出力します。

最終確認は `status` 列を `confirmed` または `excluded` に更新して運用してください。
