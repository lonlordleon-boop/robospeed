<?php
/* =========================================================================
   上位の取得
   =========================================================================
   GET / 返りは JSON。

     top.php?limit=50
     top.php?limit=50&device=0123456789abcdef   ← 自分の最高も一緒に返す

   返り:
     {"ok":true,"total":840,
      "rows":[{"rank":1,"name":"...","kills":58,"avgMs":2600,
               "fastMs":1900,"bestHand":6,"maxChain":6,
               "build":"2026-09-07a ...","at":"2026-09-04"}, ...],
      "me":{"rank":12,"kills":33,"avgMs":3900}}
   ========================================================================= */

declare(strict_types=1);
require __DIR__ . '/lib.php';

rank_preflight();

$method = isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : '';
if ($method !== 'GET') {
    rank_json(array('ok' => false, 'error' => 'method'), 405);
}

$limit = rank_int(isset($_GET['limit']) ? $_GET['limit'] : 50, 1, 100);
if ($limit === false) { $limit = 50; }

$device = isset($_GET['device']) ? (string)$_GET['device'] : '';
if (preg_match('/^[0-9a-f]{16}$/', $device) !== 1) { $device = ''; }

/* 難易度。**盤は3つある。**（仕様書 9-6k）
   ?diff=0 イージー ／ 1 ノーマル ／ 2 ハード。付いていなければノーマル。 */
$diff = rank_difficulty(isset($_GET['diff']) ? $_GET['diff'] : 1);

$db  = rank_db();
// 表の名前は config.php で決まる（1つの DB を複数のゲームで共有するため）。
$tbl = rank_table();

try {
    // **並びは schema.sql の idx_rank と同じ。** ここだけ変えると索引が効かない。
    // LIMIT にプレースホルダは使えないので、整数に通した後の値を埋め込む。
    $sql = 'SELECT name, kills, avg_ms, fast_ms, best_hand,
                   max_chain, build_ver, created_at
              FROM ' . $tbl . '
             WHERE difficulty = :d
             ORDER BY kills DESC, avg_ms ASC, id ASC
             LIMIT ' . (int)$limit;
    $st = $db->prepare($sql);
    $st->execute(array(':d' => $diff));
    $rows = $st->fetchAll();

    $out = array();
    $i = 0;
    foreach ($rows as $r) {
        $i++;
        $out[] = array(
            'rank'     => $i,
            'name'     => $r['name'],
            'kills'    => (int)$r['kills'],
            'avgMs'    => (int)$r['avg_ms'],
            'fastMs'   => (int)$r['fast_ms'],
            'bestHand' => (int)$r['best_hand'],
            // v1.12 で足した2つ（9-6m）。**順位には関わりません。**
            // 古い行は 0／空。画面側はそれを「—」と出します。
            'maxChain' => (int)$r['max_chain'],
            'build'    => (string)$r['build_ver'],
            'at'       => substr((string)$r['created_at'], 0, 10),
        );
    }

    // 人数も **その難易度だけ** 数える。「12人中3位」の分母がずれると意味が壊れる。
    $st = $db->prepare('SELECT COUNT(*) FROM ' . $tbl . ' WHERE difficulty = :d');
    $st->execute(array(':d' => $diff));
    $total = (int)$st->fetchColumn();

    // 自分の最高。**表の外にいても自分の位置が分かる**ようにするため。
    $me = null;
    if ($device !== '') {
        $st = $db->prepare(
            'SELECT kills, avg_ms FROM ' . $tbl . '
              WHERE device = :dev AND difficulty = :dif
              ORDER BY kills DESC, avg_ms ASC, id ASC
              LIMIT 1'
        );
        $st->execute(array(':dev' => $device, ':dif' => $diff));
        $row = $st->fetch();
        if ($row) {
            $me = array(
                'rank'  => rank_position($db, (int)$row['kills'], (int)$row['avg_ms'], $diff),
                'kills' => (int)$row['kills'],
                'avgMs' => (int)$row['avg_ms'],
            );
        }
    }
} catch (PDOException $e) {
    rank_json(array('ok' => false, 'error' => 'db'), 500);
}

// difficulty も返す。**どの盤を見ているのか、受け取った側でも確かめられるように。**
rank_json(array('ok' => true, 'diff' => $diff, 'total' => $total, 'rows' => $out, 'me' => $me));
