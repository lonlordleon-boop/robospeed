<?php
/* =========================================================================
   お知らせの投稿（★v1.13j・仕様書 9-6ag）
   =========================================================================
   POST / 本体は JSON。**合い言葉を知っている人だけが使えます。**

     {"key":"（合い言葉）","op":"post",
      "title":"ver 2026-09-16a を公開しました",
      "body":"連続撃破でほめ言葉が出るようになりました。",
      "ver":"2026-09-16a"}

     {"key":"…","op":"hide","id":7}    ← 出したものを引っ込める（消さずに隠す）
     {"key":"…","op":"list"}           ← 最近の10件を見る

   ■ 合い言葉の置き場所
     **gamedb.php（public_html の外）に 'newsKey' => '…' を足します。**
     パスワードと同じ扱いで、プロジェクトの中には置きません。

   ■ ここから送るのは自分だけ
     人数の多い口ではないので、連投の制限は付けていません。
   ========================================================================= */

declare(strict_types=1);
require __DIR__ . '/lib.php';
require __DIR__ . '/news_table.php';

rank_preflight();

$method = isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : '';
if ($method !== 'POST') {
    rank_json(array('ok' => false, 'error' => 'method'), 405);
}

$raw = file_get_contents('php://input');
if ($raw === false || $raw === '' || strlen($raw) > 8192) {
    rank_json(array('ok' => false, 'error' => 'body'), 400);
}
$in = json_decode($raw, true);
if (!is_array($in)) {
    rank_json(array('ok' => false, 'error' => 'json'), 400);
}

// **まず合い言葉。** 中身を見るより先に断る。
news_auth(isset($in['key']) ? $in['key'] : null);

$op  = isset($in['op']) ? (string)$in['op'] : 'post';
$db  = rank_db();
$tbl = news_table();

try {
    if ($op === 'list') {
        $st = $db->prepare(
            'SELECT id, title, ver, active, created_at FROM ' . $tbl . '
              ORDER BY id DESC LIMIT 10'
        );
        $st->execute();
        $out = array();
        foreach ($st->fetchAll() as $r) {
            $out[] = array(
                'id'     => (int)$r['id'],
                'title'  => (string)$r['title'],
                'ver'    => (string)$r['ver'],
                'active' => ((int)$r['active'] === 1),
                'at'     => substr((string)$r['created_at'], 0, 16),
            );
        }
        rank_json(array('ok' => true, 'rows' => $out));
    }

    if ($op === 'hide' || $op === 'show') {
        $id = rank_int(isset($in['id']) ? $in['id'] : null, 1, 99999999);
        if ($id === false) { rank_json(array('ok' => false, 'error' => 'id'), 400); }
        $st = $db->prepare('UPDATE ' . $tbl . ' SET active = :a WHERE id = :id');
        $st->execute(array(':a' => ($op === 'hide' ? 0 : 1), ':id' => $id));
        rank_json(array('ok' => true, 'id' => $id, 'active' => ($op === 'show')));
    }

    if ($op !== 'post') {
        rank_json(array('ok' => false, 'error' => 'op'), 400);
    }

    /* 掃除は rank_clean_text に任せる（制御文字を落として、決めた文字数で切る）。
       **本文だけは改行を残したい**ので、先に改行を目印へ逃がしてから戻します。
       ここで改行ごと落とすと、お知らせが1行の塊になって読みにくくなります。 */
    $title = rank_clean_text(isset($in['title']) ? $in['title'] : '', 60);
    $bodyIn = isset($in['body']) ? (string)$in['body'] : '';
    $bodyIn = str_replace(array("\r\n", "\r"), "\n", $bodyIn);
    /* 逃がし先は **制御文字ではない字**にすること。rank_clean_text は
       \x00〜\x1F を落とすので、\x01 に逃がすとそこで消える。
       私用領域（U+E000）はどの文書にも出てこないので、目印に使える。 */
    $body = rank_clean_text(str_replace("\n", "\u{E000}", $bodyIn), 1000);
    $body = str_replace("\u{E000}", "\n", $body);
    $ver  = rank_clean_text(isset($in['ver']) ? $in['ver'] : '', 48);

    if ($title === '' || $body === '') {
        rank_json(array('ok' => false, 'error' => 'empty'), 400);
    }

    $st = $db->prepare(
        'INSERT INTO ' . $tbl . ' (title, body, ver, active, created_at)
         VALUES (:t, :b, :v, 1, NOW())'
    );
    $st->execute(array(':t' => $title, ':b' => $body, ':v' => $ver));
    $id = (int)$db->lastInsertId();
} catch (PDOException $e) {
    rank_json(array('ok' => false, 'error' => 'db'), 500);
}

rank_json(array('ok' => true, 'id' => $id, 'title' => $title, 'ver' => $ver));
