# pompomcrawler

ポムポムプリンの新商品・イベント情報を広めに集め、確認しやすい CSV/XLSX のスケジュール表にするための CLI です。

公開カレンダー: https://main.d1tvp4oub2aan6.amplifyapp.com/

旧 GitHub Pages 版: https://koalafes.github.io/pompomcrawler/

外部検索 API や SNS API は不要です。OpenAI API キーがある場合は、取得済みページ本文から商品名・日付・場所などを構造化抽出します。取得元ページに `og:image` や本文画像がある場合は画像 URL も候補に保存し、HTML カレンダーの予定欄に表示します。キーがない場合も、固定巡回、確認チェックリスト生成、手動 CSV 取り込み、CSV 出力は動きます。

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
```

`.env` に `OPENAI_API_KEY` を設定すると、`extract` で OpenAI API による抽出が使われます。複数の worktree で同じ設定を使う場合は、`~/.config/pompomcrawler/.env` に置くと各 worktree から共通で読み込めます。worktree 側の `.env` は共通設定より優先されます。

```bash
mkdir -p ~/.config/pompomcrawler
printf 'OPENAI_API_KEY=sk-proj-...\nOPENAI_MODEL=gpt-5.4-mini\n' > ~/.config/pompomcrawler/.env
```

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
pompomcrawler extract --reprocess
pompomcrawler extract --no-openai
pompomcrawler extract --no-openai --replace
```

## Workflow

1. `crawl` でサンリオ公式、PR/ニュース媒体、公開ページを巡回します。
2. `make-checklist` で Google/X/Instagram/TikTok などの確認リンクを作ります。
3. SNS や検索で見つけた URL は `import-manual` で投入します。手動 CSV に `image_url` 列を追加すると、その画像も予定欄に表示されます。
4. `extract` で本文から候補行を作ります。
5. `export` で `outputs/pompompurin_schedule.csv`、`outputs/pompompurin_schedule.xlsx`、`outputs/pompompurin_calendar.html` を出力します。

最終確認は `status` 列を `confirmed` または `excluded` に更新して運用してください。

## AWS migration

AWS 版は `infra/` の CDK スタックで、DynamoDB、API Gateway HTTP API、Lambda、Cognito、EventBridge Scheduler を作成します。公開カレンダーは Amplify Hosting から `docs/index.html` を配信し、管理操作は Cognito の `calendar-admin` グループに入ったユーザーだけが実行できます。自動巡回は毎日 07:00 / 18:00 JST に実行します。

現在のアクセス先:

- 公開カレンダー: https://main.d1tvp4oub2aan6.amplifyapp.com/
- 公開API: https://pg2isf3a64.execute-api.ap-northeast-1.amazonaws.com/items
- Cognito Hosted UI: https://pompomcrawler-154052710150-ap-northeast-1.auth.ap-northeast-1.amazoncognito.com
- AWSリージョン: `ap-northeast-1`

```bash
cd infra
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/cdk bootstrap
.venv/bin/cdk deploy
```

デプロイ後、CDK 出力の `ApiBaseUrl`、`CognitoDomain`、`CognitoUserPoolClientId` を Amplify の環境変数に設定します。

```bash
POMPOM_API_BASE_URL=https://... \
POMPOM_COGNITO_DOMAIN=https://...auth.ap-northeast-1.amazoncognito.com \
POMPOM_COGNITO_CLIENT_ID=... \
POMPOM_COGNITO_REDIRECT_URI=https://main.xxxxx.amplifyapp.com/ \
POMPOM_COGNITO_LOGOUT_URI=https://main.xxxxx.amplifyapp.com/ \
POMPOM_NEW_LABEL_AFTER=2026-05-31T00:00:00+00:00
```

`POMPOM_NEW_LABEL_AFTER` 以降に追加された予定は、追加から24時間だけ「新着」ラベルを表示します。

既存データの初回投入は、CDK 出力のテーブル名を環境変数に入れて実行します。

```bash
SCHEDULE_ITEMS_TABLE=... DELETED_KEYS_TABLE=... RAW_DOCUMENTS_TABLE=... pompomcrawler migrate-aws
```

OpenAI API キーは Secrets Manager の `pompomcrawler/openai` に、`{"OPENAI_API_KEY":"...","OPENAI_MODEL":"..."}` 形式で保存してください。

Cognito には管理ユーザーを作成し、`calendar-admin` グループへ追加してください。このグループに入っていないユーザーは削除・復旧APIを実行できません。Amplify の標準URLが確定したら、Cognito User Pool Client の callback/logout URL にそのURLも追加してください。

## 再収集時の扱い

- `crawl` / `import-manual` は、同じ URL の raw document を重複追記しません。
- 同じ URL で本文・タイトルなどが変わっている場合は、その URL の raw document を更新します。
- 通常の `extract` は、既に `schedule_items.jsonl` に出典 URL がある raw document を再処理しません。
- 既存分も再抽出したい場合は `extract --reprocess` を使います。
- `extract --replace` は候補ファイル全体を作り直すため、手で更新した `confirmed` / `excluded` を残したい運用では慎重に使ってください。
