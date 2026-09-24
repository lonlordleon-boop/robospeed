/* =========================================================================
   docs/ から「アプリに同梱するものだけ」を app/www/ に集める
   =========================================================================

   ■ なぜ要るか
     docs/mecha は 1.4GB あるが、**ゲームが実際に読むのは 50MB 足らず。**
     残りは切り出し前の素材・不採用・実験で、アプリに入れる理由が無い。
     手で選ぶと必ず取りこぼすので、**参照しているものを機械で数える。**

   ■ 何を集めるか
     1. playtest.html を index.html として置く
     2. HTML に直接書いてあるパス
     3. 組み立てて作るパス（機体35枚・カードの色・動画5本など）
        ―― ここは **コード側と二重管理になる。** 増やしたらここも足すこと。

   ■ API の行き先を差し替える
     アプリの中では居場所が https://localhost になるので、
     "api/" という相対パスはサーバーに届かない。
     **絶対URLを window.ROBOSPEED_API として index.html に差し込む。**
     ゲーム側は window.ROBOSPEED_API があればそれを使う（無ければ "api/"）。

     使いかた:  node build-www.mjs
   ========================================================================= */

import { readFileSync, writeFileSync, mkdirSync, copyFileSync, existsSync, rmSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

const DOCS = resolve("../docs");
const WWW = resolve("www");
/* ★2026-09-09 差し替え。avfan.mixh.jp → aidgames.jp
   avfan はアダルトサイトで、**そのドメインをアプリから叩くのは避ける**（AdMob の審査を考えて）。
   ゲーム用に aidgames.jp を取り、api/ をそちらへ置いた。
   ブラウザ版（avfan 側）は今までどおり自分の api/ を相対で見にいくので、影響しない。 */
const API = "https://aidgames.jp/robospeed/api/";

const MK = ["red", "blue", "yellow", "green", "purple"];

/** HTML に文字列で書いてあるパスを拾う。 */
function staticRefs(html) {
  const out = new Set();
  const re = /["'(](?:\.\/)?((?:mecha|audio)\/[A-Za-z0-9_./-]+\.(?:png|jpg|jpeg|webp|mp4|webm|wav|mp3|ogg))["')]/g;
  let m;
  while ((m = re.exec(html)) !== null) { out.add(m[1]); }
  return out;
}

/** 実行時に組み立てるパス。**コード側を変えたら、ここも変えること。** */
function builtRefs() {
  const out = new Set();
  // 機体 7役 × 5社（MECHA_DIR + "h" + hand + "_" + 色 + ".png"）
  for (let h = 0; h <= 6; h++) { for (const c of MK) { out.add(`mecha/game/h${h}_${c}.png`); } }
  // カードの社章と印
  for (const c of MK) { out.add(`mecha/card/em_${c}.png`); }
  out.add("mecha/card/sym_go.png");
  out.add("mecha/card/sym_over.png");
  out.add("mecha/card/plate_hud.png");
  // ピュアカラーの動画 5本
  for (const c of MK) { out.add(`mecha/video/pure_${c}.mp4`); }
  return out;
}

const html = readFileSync(join(DOCS, "playtest.html"), "utf8");
const want = new Set([...staticRefs(html), ...builtRefs()]);

if (existsSync(WWW)) { rmSync(WWW, { recursive: true, force: true }); }
mkdirSync(WWW, { recursive: true });

let bytes = 0;
const missing = [];
for (const rel of [...want].sort()) {
  const src = join(DOCS, rel);
  if (!existsSync(src)) { missing.push(rel); continue; }
  const dst = join(WWW, rel);
  mkdirSync(dirname(dst), { recursive: true });
  copyFileSync(src, dst);
  bytes += statSync(dst).size;
}

/* index.html。**API の行き先だけを差し込む。**
   ゲーム本体は1文字も変えない（web版とアプリ版で中身を分けない）。 */
const inject = `<script>window.ROBOSPEED_API=${JSON.stringify(API)};</script>\n`;
let out = html;
const at = out.indexOf("<script");
if (at < 0) { throw new Error("script タグが見つからない。差し込み位置を決められない"); }
out = out.slice(0, at) + inject + out.slice(at);
writeFileSync(join(WWW, "index.html"), out);
bytes += Buffer.byteLength(out);

console.log(`集めた: ${want.size - missing.length} ファイル / ${(bytes / 1048576).toFixed(1)} MB`);
if (missing.length) {
  console.log(`\n** 見つからない ${missing.length} 件 **`);
  for (const m of missing) { console.log("  " + m); }
  process.exitCode = 1;
}
