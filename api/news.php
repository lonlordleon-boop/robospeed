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

try {
    /* active = 1 の中でいちばん新しいもの。**引っ込めたものは返さない。**
       間違えて出したお知らせを、消さずに隠せるようにするための列です。 */
    $st = $db->prepare(
        'SELECT id, title, body, ver, created_at FROM ' . $tbl . '
          WHERE active = 1 ORDER BY id DESC LIMIT 1'
    );
    $st->execute();
    $r = $st->fetch();
} catch (PDOException $e) {
    rank_json(array('ok' => false, 'error' => 'db'), 500);
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
