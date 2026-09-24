<?php
/* =========================================================================
   設置の診断
   =========================================================================
   繋がらない理由を切り分けるための一時ファイルです。

   **パスワードは出しません。** 出すのは「あるか／読めるか／鍵の名前」だけ。

   ブラウザで …/api/check.php を開いて、出た内容をそのまま伝えてください。
   **確認が済んだらサーバーから消してください。**
   ========================================================================= */

header('Content-Type: text/plain; charset=utf-8');

function line($k, $v) { echo str_pad($k, 22) . ' : ' . $v . "\n"; }
function yn($b) { return $b ? 'あり' : 'なし'; }

echo "=== 1. PHP ===\n";
line('PHP', PHP_VERSION);
line('PDO', yn(class_exists('PDO')));
line('mysql ドライバ', class_exists('PDO')
     ? (in_array('mysql', PDO::getAvailableDrivers(), true) ? 'あり' : 'なし')
     : '—');
line('mbstring', yn(function_exists('mb_substr')));
$ob = ini_get('open_basedir');
line('open_basedir', ($ob === '' || $ob === false) ? '制限なし' : $ob);
echo "\n";

echo "=== 2. 置き場所 ===\n";
line('この api/ の場所', __DIR__);
line('DOCUMENT_ROOT', isset($_SERVER['DOCUMENT_ROOT']) ? $_SERVER['DOCUMENT_ROOT'] : '（無し）');
echo "\n";

echo "=== 3. gamedb.php を探す ===\n";
$tries = array();
if (!empty($_SERVER['DOCUMENT_ROOT'])) {
    /* 第2引数は「/ と \ を削る」という意味。**単引用符の中でも \ は自分自身を escape する**ので、
       '/\' と書くと \' が引用符の escape と解釈され、文字列が閉じずに構文エラーになる。
       実際 aidgames.jp へ上げた初回、このファイルだけ 500 を返した（2026-09-09）。 */
    $tries[] = rtrim($_SERVER['DOCUMENT_ROOT'], '/\\') . '/../gamedb.php';
}
$d = __DIR__;
for ($i = 0; $i < 6; $i++) {
    $up = dirname($d);
    if ($up === $d) { break; }
    $d = $up;
    $tries[] = $d . '/gamedb.php';
}
$found = '';
foreach ($tries as $p) {
    $ex = is_file($p);
    $rd = $ex ? is_readable($p) : false;
    echo '  ' . ($rd ? '[読める]  ' : ($ex ? '[読めない]' : '[無い]    ')) . ' ' . $p . "\n";
    if ($rd && $found === '') { $found = $p; }
}
echo "\n";
line('見つかった', $found !== '' ? $found : '見つかりませんでした');
echo "\n";

echo "=== 4. 設定の中身（値は出しません）===\n";
$own = @include __DIR__ . '/config.php';
line('config.php', is_array($own) ? '読めた' : '読めない／配列でない');
if (is_array($own)) {
    line('  table', isset($own['table']) ? $own['table'] : '（無し）');
    line('  shared', (isset($own['shared']) && $own['shared'] !== '') ? $own['shared'] : '（空・自動で探す）');
}
$shared = null;
if ($found !== '') {
    $shared = @include $found;
    line('gamedb.php', is_array($shared) ? '読めた' : '読めない／配列でない');
    if (is_array($shared)) {
        line('  入っている鍵', implode(', ', array_keys($shared)));
        line('  host', isset($shared['host']) ? $shared['host'] : '（無し）');
        line('  db', isset($shared['db']) ? $shared['db'] : '（無し）');
        line('  user', isset($shared['user']) ? $shared['user'] : '（無し）');
        line('  pass', isset($shared['pass'])
             ? ($shared['pass'] === '' ? '**空**' : '入っている（' . strlen($shared['pass']) . '文字）')
             : '（無し）');
    }
}
echo "\n";

echo "=== 5. 実際に繋いでみる ===\n";
if (!is_array($shared)) {
    echo "  gamedb.php が読めていないので試せません。\n";
} else {
    $dsn = 'mysql:host=' . $shared['host'] . ';dbname=' . $shared['db'] . ';charset=utf8mb4';
    try {
        $db = new PDO($dsn, $shared['user'], $shared['pass'],
                      array(PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION));
        echo "  接続: 成功\n";
        $t = (is_array($own) && isset($own['table'])) ? $own['table'] : 'scores';
        if (preg_match('/^[A-Za-z0-9_]{1,64}$/', $t) === 1) {
            try {
                $n = $db->query('SELECT COUNT(*) FROM `' . $t . '`')->fetchColumn();
                echo "  表 `" . $t . "`: あり（" . (int)$n . " 件）\n";
            } catch (PDOException $e) {
                echo "  表 `" . $t . "`: 読めない → " . $e->getMessage() . "\n";
            }
        } else {
            echo "  表名が不正です: " . $t . "\n";
        }
    } catch (PDOException $e) {
        // **ここに出る文言が、いちばん原因を教えてくれます。**
        //   Access denied ... → ユーザー名かパスワード、または権限の割り当て忘れ
        //   Unknown database  → DB 名（接頭辞）が違う
        echo "  接続: 失敗 → " . $e->getMessage() . "\n";
    }
}
echo "\n終わり。**確認したらこのファイルは消してください。**\n";
