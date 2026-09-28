/* =========================================================================
   .gitignore を作る（★2026-09-24）
   =========================================================================

   **元データは持っていけない。** docs/mecha は 1.4GB あり、GitHub の目安（1GB）を超える。
   一方で **ゲームが実際に読む絵と音は 48MB** しかない。

   そこで「mecha は全部無視。ただし **アプリに入るものだけ戻す**」という .gitignore を作る。
   戻す一覧は **build-www.mjs と同じやり方**で数える（手で選ぶと必ず取りこぼす）。

   **絵を足したり、参照を変えたりしたら、これをもう一度走らせること。**
     node tools/make-gitignore.mjs
   ========================================================================= */

import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const ROOT = resolve(".");
const html = readFileSync(resolve("docs/playtest.html"), "utf8");
const MK = ["red", "blue", "yellow", "green", "purple"];

/* ---- build-www.mjs と同じ拾いかた ---- */
const refs = new Set();
const re = /["'(](?:\.\/)?((?:mecha|audio)\/[A-Za-z0-9_./-]+\.(?:png|jpg|jpeg|webp|mp4|webm|wav|mp3|ogg))["')]/g;
let m;
while ((m = re.exec(html)) !== null) { refs.add(m[1]); }
for (let h = 0; h <= 6; h++) { for (const c of MK) { refs.add(`mecha/game/h${h}_${c}.png`); } }
for (const c of MK) { refs.add(`mecha/card/em_${c}.png`); refs.add(`mecha/video/pure_${c}.mp4`); }
refs.add("mecha/card/sym_go.png");
refs.add("mecha/card/sym_over.png");
refs.add("mecha/card/plate_hud.png");

const mecha = [...refs].filter(p => p.startsWith("mecha/")).sort();

const body = `# =========================================================================
# git に入れないもの（tools/make-gitignore.mjs が作る・手で直さない）
# =========================================================================

# ---- 別のプロジェクト・大きすぎるもの ----
# QuarterTest は全部無視。ただし文字だけの小さいファイル（手順書・キャラクターツール・面えらび・Blender のスクリプト）は戻す
# （2026-09-28。モデル・絵は大きいので入れない）
QuarterTest/*
!QuarterTest/Tools/
QuarterTest/Tools/*
!QuarterTest/Tools/キャラ作成の手順.md
!QuarterTest/Tools/preview/
QuarterTest/Tools/preview/*
!QuarterTest/Tools/preview/preview.html
!QuarterTest/Tools/preview/facepick.html
!QuarterTest/Tools/blender/
QuarterTest/Tools/blender/*
!QuarterTest/Tools/blender/*.py
_upload/
scratchpad/

# ---- 機械が作り直せるもの ----
node_modules/
app/node_modules/
app/www/
app/android/
app/ios/
app/node_modules/
*.log

# ---- 鍵とパスワード（保険。本来この中には無い）----
*.jks
*.keystore
*.key
gamedb.php
local.properties
.gradle/
*.local.json

# ---- 絵の元データ 1.4GB ----
# **全部無視してから、アプリが実際に読むものだけ戻す。**
# 戻す一覧は playtest.html を読んで機械が作っている（${mecha.length} 個）。
docs/mecha/**
!docs/mecha/**/
${mecha.map(p => "!docs/" + p).join("\n")}
`;
writeFileSync(resolve(ROOT, ".gitignore"), body);
console.log("作った .gitignore  戻す絵 " + mecha.length + " 個");
