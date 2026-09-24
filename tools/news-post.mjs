/* =========================================================================
   お知らせを送る道具（★v1.13j・仕様書 9-6ag）
   =========================================================================

   タイトル画面に出るお知らせを、この PC から送ります。

     node tools/news-post.mjs post "ver 2026-09-16a を公開しました" "本文" 2026-09-16a
     node tools/news-post.mjs list              … 最近の10件を見る
     node tools/news-post.mjs hide 7            … 7番を引っ込める（消さない）
     node tools/news-post.mjs show 7            … 引っ込めたものを戻す

   ■ 合い言葉の置き場所
     D:/keys/robospeed-news.key   ← 鍵と同じ場所。**プロジェクトの中には置かない。**
     環境変数 ROBOSPEED_NEWS_KEY があれば、そちらを先に使います。

     サーバー側は /home/アカウント名/gamedb.php の 'newsKey' に、
     **同じ文字列**を書いておきます（public_html の外なので URL からは届きません）。

   ■ 本文の改行
     PowerShell から複数行を渡すのは面倒なので、**\n と書けば改行になります。**
       node tools/news-post.mjs post "題" "1行目\n2行目"
   ========================================================================= */

import fs from "node:fs";

const API = "https://aidgames.jp/robospeed/api/news_post.php";
const KEY_FILE = "D:/keys/robospeed-news.key";   // Windows でも / で開ける

function readKey() {
  const env = process.env.ROBOSPEED_NEWS_KEY;
  if (env && env.trim()) { return env.trim(); }
  try {
    const s = fs.readFileSync(KEY_FILE, "utf8").trim();
    if (s) { return s; }
  } catch (e) {}
  console.error("合い言葉が見つかりません。");
  console.error("  " + KEY_FILE + " に保存するか、環境変数 ROBOSPEED_NEWS_KEY に入れてください。");
  console.error("  作るなら: node -e \"console.log(require('crypto').randomBytes(24).toString('base64url'))\"");
  console.error("  **同じ文字列を、サーバーの gamedb.php の 'newsKey' にも書きます。**");
  process.exit(1);
}

/** 返りは必ず JSON のはず。**そうでなければ、そのまま見せる。** 直す場所が分かる。 */
async function send(payload) {
  const res = await fetch(API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const txt = await res.text();
  let body = null;
  try { body = JSON.parse(txt); } catch (e) {}
  if (!body) {
    console.error("返事が JSON ではありませんでした（HTTP " + res.status + "）:");
    console.error(txt.slice(0, 500));
    process.exit(1);
  }
  return { status: res.status, body };
}

const ERR = {
  auth:   "合い言葉が違います（PC 側とサーバーの gamedb.php を見比べてください）",
  nokey:  "サーバーの gamedb.php に newsKey がありません（32文字以上）",
  db:     "サーバーがデータベースに繋がっていません",
  table:  "notices の表がありません（api/schema.sql の CREATE TABLE を流してください）",
  empty:  "題か本文が空です",
  method: "送り方が違います",
  op:     "使い方が違います",
};

const [, , op = "", a1 = "", a2 = "", a3 = ""] = process.argv;
const key = readKey();

let payload;
if (op === "post") {
  if (!a1 || !a2) {
    console.error('使い方: node tools/news-post.mjs post "題" "本文" [版]');
    process.exit(1);
  }
  payload = { key, op: "post", title: a1, body: a2.replace(/\\n/g, "\n"), ver: a3 || "" };
} else if (op === "list") {
  payload = { key, op: "list" };
} else if (op === "hide" || op === "show") {
  if (!a1) { console.error("使い方: node tools/news-post.mjs " + op + " <番号>"); process.exit(1); }
  payload = { key, op, id: Number(a1) };
} else {
  console.error("使い方:");
  console.error('  node tools/news-post.mjs post "題" "本文" [版]');
  console.error("  node tools/news-post.mjs list");
  console.error("  node tools/news-post.mjs hide <番号> / show <番号>");
  process.exit(1);
}

const { status, body } = await send(payload);

if (!body.ok) {
  console.error("送れませんでした（HTTP " + status + "）: " + (ERR[body.error] || body.error || "理由不明"));
  process.exit(1);
}

if (op === "list") {
  if (!body.rows.length) { console.log("お知らせはまだありません。"); }
  for (const r of body.rows) {
    console.log([
      String(r.id).padStart(3),
      r.active ? "出ている" : "引っ込め",
      (r.ver || "—").padEnd(12),
      r.at,
      r.title,
    ].join("  "));
  }
} else if (op === "post") {
  console.log("送りました。番号 " + body.id + (body.ver ? "（版 " + body.ver + "）" : ""));
  console.log("アプリはタイトル画面を出すときに読みに行きます。**次に起動した人から**帯が出ます。");
} else {
  console.log((op === "hide" ? "引っ込めました" : "また出しました") + "。番号 " + body.id);
}
