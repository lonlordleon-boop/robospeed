<?php
/* =========================================================================
   スコアの登録
   =========================================================================
   POST / 本体は JSON。フォーム送信ではありません。

     {"name":"...","kills":33,"avgMs":3900,"fastMs":2100,
      "aliveMs":128400,"launches":41,"bestHand":5,"difficulty":1,
      "maxChain":6,"build":"2026-09-07b ...",
      "device":"0123456789abcdef"}

   maxChain / build は v1.12 で追加（9-6m）。**古い版は送ってきません。**
   来なければ 0／空で通します（送らない端末を締め出さないため）。

   返り: {"ok":true,"rank":12,"total":840}
   ========================================================================= */

declare(strict_types=1);
require __DIR__ . '/lib.php';

rank_preflight();

$cfg = rank_config();

$method = isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : '';
if ($method !== 'POST') {
    rank_json(array('ok' => false, 'error' => 'method'), 405);
}

// 本体を読む。長すぎるものは読まずに切る
$raw = file_get_contents('php://input');
if ($raw === false || $raw === '' || strlen($raw) > 2048) {
    rank_json(array('ok' => false, 'error' => 'body'), 400);
}
$in = json_decode($raw, true);
if (!is_array($in)) {
    rank_json(array('ok' => false, 'error' => 'json'), 400);
}

// ---- 名前 ----
$name = rank_clean_name(isset($in['name']) ? $in['name'] : '');
if ($name === '') {
    rank_json(array('ok' => false, 'error' => 'name'), 400);
}

// ---- 端末の識別（16桁の16進数だけ通す）----
$device = isset($in['device']) ? (string)$in['device'] : '';
if (preg_match('/^[0-9a-f]{16}$/', $device) !== 1) {
    rank_json(array('ok' => false, 'error' => 'device'), 400);
}

// ---- 数値 ----
$kills    = rank_int(isset($in['kills'])    ? $in['kills']    : null, 0, $cfg['maxKills']);
$avgMs    = rank_int(isset($in['avgMs'])    ? $in['avgMs']    : null, 0, 600000);
$fastMs   = rank_int(isset($in['fastMs'])   ? $in['fastMs']   : null, 0, 600000);
$aliveMs  = rank_int(isset($in['aliveMs'])  ? $in['aliveMs']  : null, 0, 10800000); // 3時間
$launches = rank_int(isset($in['launches']) ? $in['launches'] : null, 1, 5000);
$bestHand = rank_int(isset($in['bestHand']) ? $in['bestHand'] : null, 0, 6);

/* ---- v1.12 で足した2つ（仕様書 9-6m）----
   **どれも順位には使いません。** 見せるため・調べるための欄です。

   古いクライアントは送ってきません。**そのときは 0／空にして通す。**
   ここで弾くと、更新していない端末から一切登録できなくなります。 */
$maxChain = rank_int(isset($in['maxChain']) ? $in['maxChain'] : 0, 0, 5000);
$build    = rank_clean_text(isset($in['build']) ? $in['build'] : '', 48);

/* ---- 難易度 ----（仕様書 9-6k）
   **盤は3つある。** 0 イージー／1 ノーマル／2 ハード。
   送られてこなければノーマル扱い（difficulty 列を足す前の記録と揃う）。

   **どの難易度で走ったかはブラウザの申告なので、細工すれば嘘がつける。**
   ここは今までどおり「抑止であって防御ではない」（13-4d）の範囲。
   嘘をついても壊れるのはその盤ひとつで、他の難易度には混ざらない。 */
$diff = rank_difficulty(isset($in['difficulty']) ? $in['difficulty'] : 1);

if ($kills === false || $avgMs === false || $fastMs === false
    || $aliveMs === false || $launches === false || $bestHand === false
    || $maxChain === false) {
    rank_json(array('ok' => false, 'error' => 'range'), 400);
}

/* ---- 明らかな嘘を弾く ----
   **これは抑止で、防御ではありません。**（仕様書 13-4d）
   判定はブラウザ側にあるので、本気で細工されたら通ります。
   ここで落とすのは「人間には出せない値」だけ。腕の良い人は落としません。 */

// 1) 組み立てが人間に不可能な速さ
if ($avgMs < $cfg['minAvgMs'] || $fastMs < $cfg['minFastMs']) {
    rank_json(array('ok' => false, 'error' => 'toofast'), 422);
}
// 2) 最速が平均より遅いことはない
if ($fastMs > $avgMs) {
    rank_json(array('ok' => false, 'error' => 'mismatch_fast'), 422);
}
/* 3) 出撃していない機体は倒せない
      ---- ★v1.10 で条件を緩めた（9-6h）----
      余ったダメージを次の機体へ持ち越すようにしたので、
      **1回の出撃で複数機まとめて落ちる。** 実機で 28出撃 / 30撃破 が出て、
      正しい記録が弾かれた。1回で落とせる上限（maxKillsPerLaunch）まで許す。 */
if ($launches * $cfg['maxKillsPerLaunch'] < $kills) {
    rank_json(array('ok' => false, 'error' => 'mismatch_launch'), 422);
}
// 4) 撃破数に対して生存時間が短すぎる（1機ごとに最低限の時間はかかる）
if ($aliveMs < $kills * $cfg['minPerKillMs']) {
    rank_json(array('ok' => false, 'error' => 'mismatch_alive'), 422);
}
// 5) 出撃回数に対しても、組み立ての時間の合計は生存時間を超えない
if ($launches * $cfg['minAvgMs'] > $aliveMs + 1000) {
    rank_json(array('ok' => false, 'error' => 'mismatch_build'), 422);
}
/* 6) 撃った回数より多く連続では撃てない（v1.12・9-6m）
      **辻褄の確認だけ。** ここも抑止であって防御ではありません。
      max_chain は順位に使わないので、嘘をつかれても順位は動きません。 */
if ($maxChain > $launches) {
    rank_json(array('ok' => false, 'error' => 'mismatch_chain'), 422);
}

$db  = rank_db();
// 表の名前は config.php で決まる（1つの DB を複数のゲームで共有するため）。
// 英数字と _ 以外は rank_table() が通さない。
$tbl = rank_table();

/* ---- 1端末1行。自己ベストのときだけ書き換える ----

   送るたびに行を増やしていた頃は、1人が10回遊べば上位が全部その人で埋まった。
   **順位表は「各人の最高記録が1つずつ並ぶ」もの。**

   鍵は名前ではなく端末（device）。名前は自由入力なので、
   **鍵にすると1位の人と同じ名前を名乗って上書きできてしまう。**
   代わりに、同じ人がスマホと PC で遊ぶと2行になる（保存データ自体が端末ごとに別）。

   名前は毎回いちばん新しいものに更新する。改名しても行は1つのまま。

   ---- ★v1.11 で「1端末1行」→「1端末×難易度で1行」に変えた（9-6k）----
   盤が3つに分かれたので、**同じ端末でも難易度ごとに別の自己ベストを持つ。**
   device だけで引くと、ハードの記録がイージーの行を上書きしてしまう。 */
try {
    $st = $db->prepare(
        'SELECT id, kills, avg_ms FROM ' . $tbl
        . ' WHERE device = :dev AND difficulty = :dif'
        . ' ORDER BY kills DESC, avg_ms ASC, id ASC LIMIT 1'
    );
    $st->execute(array(':dev' => $device, ':dif' => $diff));
    $old = $st->fetch();

    if (!$old) {
        // ---- 初めての端末 ----
        // 連投を抑えるのは **行が増える側だけ。**
        // 更新は1行を書き換えるだけなので、いくら送られても表は荒れない。
        // ここを更新にも掛けると、短い走りを続けたときに弾かれて不便になる。
        $sql = 'SELECT COUNT(*) FROM ' . $tbl . ' WHERE ip_hash = :ip'
             . ' AND created_at > (NOW() - INTERVAL ' . (int)$cfg['cooldownSec'] . ' SECOND)';
        // INTERVAL にプレースホルダは使えない（MySQL が prepare の時点で断る）ので、
        // **整数に通した後の値だけ**を埋め込む。ip_hash は今までどおり束縛する。
        $st = $db->prepare($sql);
        $st->execute(array(':ip' => rank_ip_hash()));
        if ((int)$st->fetchColumn() > 0) {
            rank_json(array('ok' => false, 'error' => 'cooldown',
                            'waitSec' => (int)$cfg['cooldownSec']), 429);
        }

        $st = $db->prepare(
            'INSERT INTO ' . $tbl . '
               (name, kills, avg_ms, fast_ms, alive_ms, launches, best_hand,
                difficulty, max_chain, build_ver,
                device, ip_hash, created_at)
             VALUES
               (:name, :kills, :avg, :fast, :alive, :launches, :hand,
                :diff, :chain, :build,
                :device, :ip, NOW())'
        );
        $st->execute(array(
            ':name'     => $name,
            ':kills'    => $kills,
            ':avg'      => $avgMs,
            ':fast'     => $fastMs,
            ':alive'    => $aliveMs,
            ':launches' => $launches,
            ':hand'     => $bestHand,
            ':diff'     => $diff,
            ':chain'    => $maxChain,
            ':build'    => $build,
            ':device'   => $device,
            ':ip'       => rank_ip_hash(),
        ));
        $improved = true;
        $bestKills = $kills;
        $bestAvg   = $avgMs;
    } else {
        // ---- 2回目以降 ----
        // **良し悪しの基準は順位の並びと同じ。** ここだけ別の物差しにすると、
        // 「自己ベストなのに順位が下がった」が起きる。
        $oldKills = (int)$old['kills'];
        $oldAvg   = (int)$old['avg_ms'];
        $improved = ($kills > $oldKills) || ($kills === $oldKills && $avgMs < $oldAvg);

        if ($improved) {
            $st = $db->prepare(
                /* 行の中身は **まるごと今回の走りのもの**に置き換える。
                   連続攻撃だけを別に「歴代最高」で持つと、
                   **表の1行が2つの走りの寄せ集め**になり、検算ができなくなる。
                   ここは「自己ベストの走りの記録」であって、通算の成績ではない。 */
                'UPDATE ' . $tbl . ' SET
                   name = :name, kills = :kills, avg_ms = :avg, fast_ms = :fast,
                   alive_ms = :alive, launches = :launches, best_hand = :hand,
                   max_chain = :chain, build_ver = :build,
                   ip_hash = :ip, created_at = NOW()
                 WHERE id = :id'
            );
            $st->execute(array(
                ':name'     => $name,
                ':kills'    => $kills,
                ':avg'      => $avgMs,
                ':fast'     => $fastMs,
                ':alive'    => $aliveMs,
                ':launches' => $launches,
                ':hand'     => $bestHand,
                ':chain'    => $maxChain,
                ':build'    => $build,
                ':ip'       => rank_ip_hash(),
                ':id'       => (int)$old['id'],
            ));
            $bestKills = $kills;
            $bestAvg   = $avgMs;
        } else {
            // 届かなかったときは **何も書かない。** 自己ベストが消えないように。
            // 名前だけは最新にしておく（改名がすぐ反映されないと直せなくなる）。
            $st = $db->prepare('UPDATE ' . $tbl . ' SET name = :name WHERE id = :id');
            $st->execute(array(':name' => $name, ':id' => (int)$old['id']));
            $bestKills = $oldKills;
            $bestAvg   = $oldAvg;
        }
    }

    // 順位は **表に載っている記録**（＝自己ベスト）を、**同じ難易度の中で**数える
    $rank  = rank_position($db, $bestKills, $bestAvg, $diff);
    $st = $db->prepare('SELECT COUNT(*) FROM ' . $tbl . ' WHERE difficulty = :d');
    $st->execute(array(':d' => $diff));
    $total = (int)$st->fetchColumn();
} catch (PDOException $e) {
    rank_json(array('ok' => false, 'error' => 'db'), 500);
}

rank_json(array(
    'ok'       => true,
    'rank'     => $rank,
    'total'    => $total,
    'diff'     => $diff,             // どの盤に載ったか（9-6k）
    'name'     => $name,
    'improved' => $improved,          // 自己ベストを更新したか
    'best'     => array('kills' => $bestKills, 'avgMs' => $bestAvg),
));
