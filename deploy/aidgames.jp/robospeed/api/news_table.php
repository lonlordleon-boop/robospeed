<?php
/* =========================================================================
   お知らせの表の名前（★v1.13j）
   =========================================================================
   **lib.php は触らずに済ませる**方針なので、お知らせ用の小さな共通処理は
   こちらに分けました。news.php と news_post.php の両方から読みます。

   表の名前はプレースホルダで束縛できないため、英数字と _ 以外は通しません。
   ========================================================================= */

declare(strict_types=1);

function news_table()
{
    $c = rank_config();
    $t = isset($c['newsTable']) ? (string)$c['newsTable'] : 'notices';
    if (preg_match('/^[A-Za-z0-9_]{1,64}$/', $t) !== 1) {
        rank_json(array('ok' => false, 'error' => 'table'), 500);
    }
    return '`' . $t . '`';
}

/**
 * 送信の合い言葉を確かめる。
 *
 * **合い言葉は gamedb.php に置きます**（public_html の外）。
 * 短い合い言葉は総当たりで破られるので、**32文字未満は最初から受け付けません。**
 * 比べるときは hash_equals を使います（1文字ずつ比べる普通の比較は、
 * 返事の速さの違いから答えが漏れることがあるため）。
 */
function news_auth($given)
{
    $c = rank_config();
    $key = isset($c['newsKey']) ? (string)$c['newsKey'] : '';
    if ($key === '' || strlen($key) < 32) {
        rank_json(array('ok' => false, 'error' => 'nokey'), 500);
    }
    if (!is_string($given) || !hash_equals($key, $given)) {
        // **理由を細かく返さない。** 合い言葉を探る手がかりになる。
        rank_json(array('ok' => false, 'error' => 'auth'), 401);
    }
}
