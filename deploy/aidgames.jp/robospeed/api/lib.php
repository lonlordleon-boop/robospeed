<?php
/* =========================================================================
   ロボ・スピード オンラインランキング — 共通処理
   =========================================================================
   設定は config.php、テーブルは schema.sql。**このファイルは触らずに済むように
   書いています。** 直したくなったら、まず config.php で足りないかを見てください。
   ========================================================================= */

declare(strict_types=1);

/**
 * 共有の接続情報（gamedb.php）を探す。
 *
 * **パスワードは public_html の外に置く。** URL から届かない場所なので、
 * .htaccess が効かなくなっても、PHP が止まっても読まれない。
 * 置き場所はアカウントごとに違うので、書かせずに探す。
 */
function rank_find_shared($hint)
{
    $tries = array();
    // 1) config.php に絶対パスが書いてあれば、それを最優先
    if (is_string($hint) && $hint !== '') { $tries[] = $hint; }
    // 2) 公開フォルダの1つ上（MixHost の標準: /home/アカウント/public_html の親）
    if (!empty($_SERVER['DOCUMENT_ROOT'])) {
        $tries[] = rtrim($_SERVER['DOCUMENT_ROOT'], '/\\') . '/../gamedb.php';
    }
    // 3) この api/ から上へ順に。階層の深さが違っても見つかるように
    $d = __DIR__;
    for ($i = 0; $i < 6; $i++) {
        $up = dirname($d);
        if ($up === $d) { break; }   // これ以上は上がれない
        $d = $up;
        $tries[] = $d . '/gamedb.php';
    }
    foreach ($tries as $p) {
        if (is_file($p) && is_readable($p)) { return $p; }
    }
    return '';
}

/**
 * 設定を読む。何度呼んでも読み込みは1回。
 * このゲームの設定（config.php）に、共有の接続情報を重ねて返す。
 */
function rank_config()
{
    static $cfg = null;
    if ($cfg !== null) { return $cfg; }

    $own = require __DIR__ . '/config.php';

    $path = rank_find_shared(isset($own['shared']) ? $own['shared'] : '');
    if ($path === '') {
        // **理由を残す。** ここで黙って落ちると「db」と区別が付かない。
        $cfg = $own;
        $cfg['__noshared'] = true;
        return $cfg;
    }
    $shared = require $path;
    if (!is_array($shared)) {
        $cfg = $own;
        $cfg['__noshared'] = true;
        return $cfg;
    }
    // 接続情報が勝つ。**このゲームの設定に host/db/user/pass は書かせない。**
    $cfg = array_merge($own, $shared);
    return $cfg;
}

/**
 * 表の名前。**1つの DB を複数のゲームで共有するので、ここで分かれる。**
 * 表名はプレースホルダで束縛できないため、英数字と _ 以外は通さない。
 */
function rank_table()
{
    $c = rank_config();
    $t = isset($c['table']) ? (string)$c['table'] : '';
    if (preg_match('/^[A-Za-z0-9_]{1,64}$/', $t) !== 1) {
        rank_json(array('ok' => false, 'error' => 'table'), 500);
    }
    return '`' . $t . '`';
}

/**
 * 返事はいつも JSON。
 * **エラーでも HTML を返さない。** PHP の警告がそのまま出ると、
 * ゲーム側の JSON.parse が落ちて「繋がらない」ではなく「壊れた」に見える。
 */
function rank_json($body, $status = 200)
{
    $cfg = rank_config();
    if (!headers_sent()) {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        header('Access-Control-Allow-Origin: ' . $cfg['origin']);
        header('Access-Control-Allow-Headers: Content-Type');
        header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
        header('Cache-Control: no-store');
    }
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/**
 * ブラウザの事前問い合わせ。api/ とゲームが違うドメインにあると必ず先に来る。
 * ここで中身なしを返さないと、本番の POST が始まらない。
 */
function rank_preflight()
{
    $m = isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : '';
    if ($m === 'OPTIONS') { rank_json(array('ok' => true), 204); }
}

/** MySQL に繋ぐ。 */
function rank_db()
{
    $c = rank_config();
    // 共有ファイルが見つからないと、接続情報そのものが無い。
    // **「DBに繋がらない」ではなく「設定が無い」と返す。** 直す場所が変わるため。
    if (!empty($c['__noshared']) || !isset($c['host'], $c['db'], $c['user'])) {
        rank_json(array('ok' => false, 'error' => 'noconf'), 500);
    }
    $dsn = 'mysql:host=' . $c['host'] . ';dbname=' . $c['db'] . ';charset=utf8mb4';
    try {
        return new PDO($dsn, $c['user'], $c['pass'], array(
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            // プレースホルダは MySQL 側で処理させる（見せかけの置換にしない）
            PDO::ATTR_EMULATE_PREPARES   => false,
        ));
    } catch (PDOException $e) {
        // **例外の本文をそのまま返さない。** DB名・ユーザー名・パスまで載る。
        rank_json(array('ok' => false, 'error' => 'db'), 500);
    }
}

/**
 * 名前の掃除。
 * 自由入力にしたので、**順位表の見た目を壊す文字だけ**を落とす。
 * 絵文字や記号はそのまま通す（utf8mb4 なので入る）。
 */
function rank_clean_name($s)
{
    if (!is_string($s)) { return ''; }
    // 制御文字（改行・タブ含む）を落とす。1行に収める
    $s = preg_replace('/[\x00-\x1F\x7F]/u', '', $s);
    if ($s === null) { return ''; }   // 不正な UTF-8 だと null が返る
    // 見えない空白で行を伸ばす手を塞ぐ
    $s = preg_replace('/[\x{200B}-\x{200D}\x{2060}\x{FEFF}]/u', '', $s);
    if ($s === null) { return ''; }
    // 連続する空白は1つに
    $s = preg_replace('/\s+/u', ' ', $s);
    if ($s === null) { return ''; }
    $s = trim($s);
    // mbstring が入っていないサーバーもある。**そこで落とさない。**
    if (function_exists('mb_substr')) {
        return mb_substr($s, 0, 12, 'UTF-8');
    }
    // 控え：文字の境目を壊さずに12文字で切る
    if (preg_match('/^(?:.){0,12}/u', $s, $m) === 1) { return $m[0]; }
    return substr($s, 0, 12);
}

/**
 * 版などの短い文字列を掃除する。（v1.12・9-6m）
 *
 * **名前（rank_clean_name）とは別に用意する。** あちらは12文字で切る決め打ちで、
 * 順位表に出す前提の掃除。こちらは中身を運ぶだけの欄なので、長さだけ変えたい。
 * 掃除の中身は同じ ―― 制御文字を落として、決めた文字数で切る。
 */
function rank_clean_text($s, $max)
{
    if (!is_string($s)) { return ''; }
    // 制御文字（改行・タブ含む）を落とす。**不正な UTF-8 だと null が返る。**
    $s = preg_replace('/[\x00-\x1F\x7F]/u', '', $s);
    if ($s === null) { return ''; }
    $s = trim($s);
    if (function_exists('mb_substr')) {
        return mb_substr($s, 0, (int)$max, 'UTF-8');
    }
    // 控え：文字の境目を壊さずに切る
    if (preg_match('/^(?:.){0,' . (int)$max . '}/u', $s, $m) === 1) { return $m[0]; }
    return substr($s, 0, (int)$max);
}

/** 整数を取り出す。範囲外・数字でないものは false。 */
function rank_int($v, $min, $max)
{
    if (is_bool($v) || !is_numeric($v)) { return false; }
    $n = (int)$v;
    if ($n < $min || $n > $max) { return false; }
    return $n;
}

/** IP のハッシュ。**IP そのものは保存しない。** */
function rank_ip_hash()
{
    $ip = isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '0.0.0.0';
    return substr(hash('sha256', 'robospeed|' . $ip), 0, 16);
}

/**
 * 順位を数える。
 * **schema.sql の idx_rank と同じ並び**（撃破数の多い順、同数なら平均が速い順）。
 * ここを変えるなら索引と top.php も一緒に変えること。
 */
function rank_position(PDO $db, $kills, $avgMs, $diff = 1)
{
    /* **難易度ごとに別の盤。**（仕様書 9-6k）
       イージーの記録がハードの順位に混ざると、順位そのものが意味を失う。
       $diff を必ず渡すこと。既定の 1（ノーマル）は、difficulty 列を足す前の
       記録がすべてノーマルであることに合わせてある。 */
    $st = $db->prepare(
        'SELECT COUNT(*) + 1 FROM ' . rank_table()
        . ' WHERE difficulty = :d AND (kills > :k1 OR (kills = :k2 AND avg_ms < :a))'
    );
    $st->execute(array(':d' => (int)$diff, ':k1' => $kills, ':k2' => $kills, ':a' => $avgMs));
    return (int)$st->fetchColumn();
}

/**
 * 難易度を 0..2 に丸める。**範囲の外は黙ってノーマルにする。**
 * ここで弾かないのは、古いクライアント（difficulty を送らない版）が
 * 残っていても登録できるようにするため。
 *   0 = イージー ／ 1 = ノーマル ／ 2 = ハード
 */
function rank_difficulty($v)
{
    $n = (int)$v;
    return ($n >= 0 && $n <= 2) ? $n : 1;
}
