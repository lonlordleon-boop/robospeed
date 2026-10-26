<?php
/* =========================================================================
   お知らせの取得（★v1.13j・仕様書 9-6ag）
   =========================================================================
   GET / 返りは JSON。**いちばん新しい1件だけ**を返します。

     news.php

   返り:
     {"ok":true,"news":{"id":7,"title":"...","body":"...",
                        "ver":"2026-09-16a","at":"2026-09-16"}}
     お知らせが1件も無いときは {"ok":true,"news":null}

   ■ なぜ要るか
     更新のお知らせを Google グループに書いても、**メールは読まれません。**
     テスターから「タイトル画面で知らせてほしい」と言われて作りました。

   ■ 個人情報は受け取りません
     読むだけの口です。端末の識別も名前も送らせません。

   ■ 片方の OS だけの更新（2026-10-26）
     ver を「android:2026-10-26a」「ios:2026-10-26a」と書くと、**その OS にだけ配ります。**
     もう片方の OS には、その帯を飛ばして1つ前の帯を返します（読んだ帯なら何も出ない）。
     アプリに返す ver からは「android:」を外すので、アプリ側は今までどおり版を見比べるだけ。
     **アプリを出し直さずに効く**ように、見分けはサーバーでやっています。
     見分けには、ブラウザが自分で付けて送ってくる User-Agent を使います
     （Android の WebView は必ず "Android" を含む。それ以外は iPhone 扱い）。
     片方だけを出し直したとき、ver を空にするとボタンが出ず、ver をそのまま入れると
     もう片方にも「新しい版」と更新ボタンが出てしまう。そのための書き方です。
   ========================================================================= */

declare(strict_types=1);
require __DIR__ . '/lib.php';
require __DIR__ . '/news_table.php';

rank_preflight();

$method = isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : '';
if ($method !== 'GET') {
    rank_json(array('ok' => false, 'error' => 'method'), 405);
}

$db  = rank_db();
$tbl = news_table();

// 頼んできた端末の OS（上の「片方の OS だけの更新」）
$ua = isset($_SERVER['HTTP_USER_AGENT']) ? (string)$_SERVER['HTTP_USER_AGENT'] : '';
$os = (stripos($ua, 'Android') !== false) ? 'android' : 'ios';

try {
    /* active = 1 の中でいちばん新しいもの。**引っ込めたものは返さない。**
       間違えて出したお知らせを、消さずに隠せるようにするための列です。
       よその OS 向けを飛ばすぶん、新しい順に少し多めに読んでおく。 */
    $st = $db->prepare(
        'SELECT id, title, body, ver, created_at FROM ' . $tbl . '
          WHERE active = 1 ORDER BY id DESC LIMIT 10'
    );
    $st->execute();
    $rows = $st->fetchAll();
} catch (PDOException $e) {
    rank_json(array('ok' => false, 'error' => 'db'), 500);
}

$r = null;
foreach ($rows as $row) {
    $m = array();
    if (preg_match('/^(android|ios):(.*)$/', (string)$row['ver'], $m) === 1) {
        if ($m[1] !== $os) { continue; }   // よその OS 向け
        $row['ver'] = $m[2];               // アプリには版だけを渡す
    }
    $r = $row;
    break;
}

if (!$r) { rank_json(array('ok' => true, 'news' => null)); }

rank_json(array('ok' => true, 'news' => array(
    'id'    => (int)$r['id'],
    'title' => (string)$r['title'],
    'body'  => (string)$r['body'],
    // その版がアプリに届いているかを、アプリ側が自分の版と見比べます（空なら見比べない）
    'ver'   => (string)$r['ver'],
    'at'    => substr((string)$r['created_at'], 0, 10),
)));
