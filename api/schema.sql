-- =========================================================================
-- ロボ・スピード オンラインランキング — テーブル定義
-- =========================================================================
--
-- ■ MixHost（cPanel）での使い方
--
--   1. cPanel →「MySQL データベース」で **データベースを作る**
--      入力欄に robospeed と打つと、実際の名前は
--        アカウント名_robospeed
--      になります（**接頭辞は外せません**）。
--   2. 同じ画面で **ユーザーを作り**、1で作った DB に
--      「すべての権限」で **割り当てる**（この割り当てを忘れると繋がりません）。
--   3. cPanel → phpMyAdmin で、左から 1 の DB を選び、
--      SQL タブに **このファイルの中身をそのまま貼って実行**。
--   4. api/config.php の 'db' と 'user' に、接頭辞込みの名前を書く。
--      'host' は 'localhost' のままで通ります。
--
-- **CREATE DATABASE はここに書いていません。** cPanel の共有サーバーでは
-- その権限が無く、書いてあると 1044 エラーでここから先が全部止まるためです。
-- DB を自分で作れる環境（VPS・ローカル）なら、先に手で作ってください:
--   CREATE DATABASE robospeed DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
--
-- 文字コードは utf8mb4。名前を自由入力にしたので、絵文字が入っても壊れません
-- （utf8 のままだと絵文字で INSERT が落ちます）。
-- =========================================================================

-- 表の名前は api/config.php の 'table' と **必ず揃えること。**
-- 1つの DB を複数のゲームで共有するので、次のゲームでは
-- 両方を別の名前にしてください（例: puzzle_scores）。
CREATE TABLE IF NOT EXISTS scores (
  id         BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,

  name       VARCHAR(12)       NOT NULL,  -- 自由入力・12文字まで
  kills      SMALLINT UNSIGNED NOT NULL,  -- 撃破数。**順位の主軸**
  avg_ms     INT UNSIGNED      NOT NULL,  -- 平均の組み立て。**同数のときの順位**
  fast_ms    INT UNSIGNED      NOT NULL,  -- 最速の組み立て（表示用）
  alive_ms   INT UNSIGNED      NOT NULL,  -- 生き延びた時間（検算用）
  launches   SMALLINT UNSIGNED NOT NULL,  -- 出撃回数（検算用）
  best_hand  TINYINT UNSIGNED  NOT NULL,  -- いちばん良かった役 0..6（表示用）

  -- 難易度。**盤は3つに分かれる。**（仕様書 9-6k）
  --   0 = イージー ／ 1 = ノーマル ／ 2 = ハード
  -- 既定を 1 にしてあるのは、**この列を足す前の記録がすべてノーマル**だから。
  -- 古いクライアント（difficulty を送らない版）が残っていても、そのまま入る。
  difficulty TINYINT UNSIGNED  NOT NULL DEFAULT 1,

  -- ---- v1.12 で足した2つ（仕様書 9-6m）----
  -- どれも **順位には使いません。** 順位は今までどおり kills → avg_ms の順。
  -- ここに入れるのは「見せるため」と「調べるため」。
  --
  -- 最高連続攻撃。敵に殴られるまでに続けて撃てた回数。
  -- 敵の組み立てが遅い序盤ほど伸びるので、**手数の稼ぎかた**がそのまま出る。
  max_chain  SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  -- **どの版のクライアントで出た記録か。**
  -- バランスを変えた前後を切り分けるための欄です。これが無かったため、
  -- 「イージーを遅くしたのに記録が変わらない」を調べたとき、
  -- 旧版で出た記録と新版の記録が区別できませんでした。
  -- 既定を空にしてあるのは、**この列を足す前の記録には版が無い**から。
  build_ver  VARCHAR(48)       NOT NULL DEFAULT '',

  -- 端末の識別。ログインが無いので、**連投を抑えるためだけ**に使います。
  -- ブラウザが自分で作った乱数で、個人を特定するものではありません。
  device     CHAR(16)          NOT NULL,
  -- IP はそのままでは保存しません（個人情報になる）。ハッシュの先頭だけ。
  ip_hash    CHAR(16)          NOT NULL,

  created_at DATETIME          NOT NULL,

  PRIMARY KEY (id),

  -- 並び順そのままの索引。**まず難易度で絞ってから**、撃破数の多い順、
  -- 同数なら平均組み立ての速い順。
  -- **この順番を変えるなら、top.php の ORDER BY も一緒に変えること。**
  KEY idx_rank (difficulty, kills DESC, avg_ms ASC),

  -- **1端末×難易度で1行。**（v1.11・9-6k）
  -- 同じ端末から送られたら、その難易度の自己ベストのときだけ書き換える。
  -- 送るたびに行を増やすと、1人が10回遊んだだけで上位が埋まってしまう。
  --
  -- device だけの UNIQUE にすると、**ハードの記録がイージーの行を潰す。**
  -- 盤が3つある以上、鍵も2列でなければならない。
  -- 付けなくても submit.php 側で1行にまとめます（保険の索引です）。
  UNIQUE KEY uq_device_diff (device, difficulty),

  -- 連投制限で「直前に登録した相手」を引くため
  KEY idx_ip (ip_hash, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =========================================================================
-- 【移行】すでに scores を作ってある場合（v1.10 → v1.11・難易度の追加）
-- =========================================================================
--
-- **上の CREATE TABLE は「これから作る人」向けです。**
-- すでに表があるなら、下の3行だけを phpMyAdmin の SQL タブで流してください。
--
-- **いまの記録は消えません。** difficulty が付いていない行は
-- DEFAULT 1 でノーマル扱いになります。実際その値で遊んだ記録なので、正しい。
--
-- 索引を張り替えるのは、盤が3つに分かれたから。
--   ・idx_rank は「まず難易度で絞る」形にしないと効かない
--   ・uq_device のままだと **ハードの記録がイージーの行を潰す**
--
-- ALTER TABLE scores
--   ADD COLUMN difficulty TINYINT UNSIGNED NOT NULL DEFAULT 1 AFTER best_hand;
--
-- ALTER TABLE scores
--   DROP INDEX idx_rank,
--   ADD KEY idx_rank (difficulty, kills DESC, avg_ms ASC);
--
-- ALTER TABLE scores
--   DROP INDEX uq_device,
--   ADD UNIQUE KEY uq_device_diff (device, difficulty);
--
-- ※ uq_device を作っていなければ、3本目は DROP INDEX を外して
--    ADD UNIQUE KEY uq_device_diff (device, difficulty); だけにしてください。
-- =========================================================================


-- =========================================================================
-- 【移行】v1.11 → v1.12（最高連続攻撃と版の追加）
-- =========================================================================
--
-- **すでに scores を作ってあるなら、この1本だけを流してください。**
-- 索引は張り替えません。**2つとも順位には使わない**ので、
-- 並び順（kills → avg_ms）は今までと1文字も変わりません。
--
-- **いまの記録は消えません。** 古い行は
--   max_chain = 0 ／ build_ver = 空文字
-- になります。0 と空欄は「測っていなかった」という意味で、
-- 画面では「—」と出ます（0回という記録ではありません）。
--
-- ALTER TABLE scores
--   ADD COLUMN max_chain SMALLINT UNSIGNED NOT NULL DEFAULT 0  AFTER difficulty,
--   ADD COLUMN build_ver VARCHAR(48)       NOT NULL DEFAULT '' AFTER max_chain;
--
-- ※ phpMyAdmin は流す前に「本当に実行しますか？」と聞いてきます。エラーではありません。
--
-- ■ #1060 - 列名 'max_chain' は重複してます。と出たら
--   **エラーではなく「もう入っている」という意味です。** 流す必要はありません。
--   `SHOW COLUMNS FROM scores;` で並びを確かめてください。
--
-- ■ multi_kill という列があったら
--   一度は入れて、あとで外した列です（仕様書 9-6m）。
--   **放置しても壊れません。** NOT NULL DEFAULT 0 なので、
--   submit.php が値を入れなくても既定の 0 が入ります。消すなら:
--     ALTER TABLE scores DROP COLUMN multi_kill;
-- =========================================================================


-- =========================================================================
-- 【全消し】記録をまっさらにする ★v1.12
-- =========================================================================
--
-- **戻せません。** 実行した瞬間に、全員の記録が消えます。
-- phpMyAdmin が出す「本当に実行しますか？」が、最後の確認になります。
--
-- ■ いつ使うか
--   測る中身が大きく変わって、**古い記録と新しい記録を同じ表に並べられない**とき。
--   v1.12 がまさにそれで、古い行には
--   最高連続攻撃と版が入っていません（0 と空欄）。
--   混ぜたままにすると、順位表の内訳が「—」だらけになります。
--
-- ■ 消す前に控えておく
--   消してしまうと、誰が何機だったか **どこにも残りません。**
--   惜しければ、phpMyAdmin の「エクスポート」で先に落としてください。
--   （scores を選び → エクスポート → 実行。SQL ファイルが1つ落ちます）
--
-- ■ 端末側の自己ベストは消えません
--   「自己ベスト◯機」はブラウザの中（localStorage）にあります。
--   サーバーを空にしても、遊ぶ人の画面には前の自己ベストが出たままです。
--   **表は空なのに自己ベストだけ高い**という状態になりますが、不具合ではありません。
--   気になるなら、遊ぶ人にサイトデータを消してもらうしかありません（図鑑も消えます）。

-- ---- 1. 全部消す（いちばん普通の道）----
-- 行を全部消して、id の採番も 1 に戻ります。
--
-- TRUNCATE TABLE scores;

-- ---- 2. 難易度をひとつだけ消す ----
-- 0 = イージー ／ 1 = ノーマル ／ 2 = ハード
-- **TRUNCATE では条件を付けられない**ので、こちらは DELETE を使います。
-- （id の採番は戻りません。並びには関係しないので、そのままで構いません）
--
-- DELETE FROM scores WHERE difficulty = 0;

-- ---- 3. 表ごと作り直す（v1.12 の列がまだ無いとき）----
-- ALTER を流さずに済ませたいなら、こちら。
-- **DROP を実行したあと、必ずこのファイルの上にある CREATE TABLE を流すこと。**
-- 流し忘れると表そのものが無くなり、登録も順位表も 'db' エラーになります。
--
-- DROP TABLE scores;
-- （↑のあと、このファイル冒頭の CREATE TABLE IF NOT EXISTS scores (...) を貼って実行）

-- ---- 4. 消したか確かめる ----
-- 0 が返れば空です。
--
-- SELECT COUNT(*) FROM scores;
-- =========================================================================


-- =========================================================================
-- お知らせ（★v1.13j・仕様書 9-6ag）
-- =========================================================================
--
-- **更新をタイトル画面で知らせるための表です。** 記録とは何の関係もありません。
-- グループへの投稿（メール）は読まれないという、テスターからの声で足しました。
--
-- すでに scores を作ってあるサーバーでも、**この CREATE TABLE だけを流せば足ります。**
-- scores には一切触りません。
--
-- 表の名前は api/config.php の 'newsTable' と揃えること（既定は notices）。
CREATE TABLE IF NOT EXISTS notices (
  id         BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,

  title      VARCHAR(60)      NOT NULL,             -- 帯に出る一行
  body       VARCHAR(1000)    NOT NULL,             -- 開いたときの本文（改行あり）

  -- **その版がアプリに届いているか**を、アプリ側が自分の版（BUILD）と見比べます。
  -- 空なら見比べません（お知らせだけ・更新ではないとき）。
  -- 書き方は BUILD の先頭と同じ「2026-09-16a」。
  ver        VARCHAR(48)      NOT NULL DEFAULT '',

  -- 間違えて出したときに **消さずに引っ込める**ための列。
  -- news.php は active = 1 のものしか返しません。
  active     TINYINT UNSIGNED NOT NULL DEFAULT 1,

  created_at DATETIME         NOT NULL,

  PRIMARY KEY (id),
  -- 「いちばん新しい、出ているもの」を1件引くだけなので、索引もその形にする
  KEY idx_live (active, id DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---- 出したお知らせを見る ----
-- SELECT id, active, ver, title, created_at FROM notices ORDER BY id DESC;
--
-- ---- 引っ込める（消さない）----
-- UPDATE notices SET active = 0 WHERE id = 1;
-- =========================================================================
