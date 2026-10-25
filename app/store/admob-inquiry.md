# AdMob への問い合わせ — Android 版に広告が配信されない（2026-10-24）

> AdMob ヘルプ →「お問い合わせ」に貼る文。**事実だけを書く。** 推測は書かない。
> こちらで確かめたことは仕様書 15-7 にまとまっている。

---

## 件名

```
Android アプリが「準備完了」なのに、全リクエストが HTTP 403 / エラーコード 3 で拒否される
```

## 本文

```
ROBO SPEED（Android）について、承認済みにもかかわらず広告が一切配信されない状態が続いています。
原因の調査をお願いします。

■ アプリ
- パブリッシャー ID：pub-2313067186861650
- Android アプリ ID：ca-app-pub-2313067186861650~1860567458
- パッケージ名：jp.aid.robospeed（Google Play で公開中・2026-10-13 公開）
- 承認状況：準備完了／広告配信を有効化（承認メールは 2026-10-14 受信）
- ポリシーセンター：問題なし・不承認なし
- 広告ユニット（いずれも Android アプリ配下・バナー）：
    結果画面  ca-app-pub-2313067186861650/8641598226
    一時停止  ca-app-pub-2313067186861650/6921322445

■ 症状
- AdMob ネットワークのレポート（過去30日・2026-09-24〜10-23）で、
  Android アプリの行が存在しない（広告リクエスト 0・表示回数 0）。
  Google Play のインストール済みユーザーは 16 です。
- 実機（Pixel 9a・Android 17・Google Play 開発者サービス 26.40）で
  本番ユニットを要求すると、SDK ログに次が出ます：
    W Ads: Received error HTTP response code: 403
    I Ads: Ad failed to load : 3
- 同じ端末・同じアプリの構成で、Google のテスト用ユニット
  （ca-app-pub-3940256099942544/6300978111）に切り替えると広告は正常に表示されます。
  → SDK の初期化・プラグイン・表示処理に問題はありません。
- 同一アカウントの iOS 版（ca-app-pub-2313067186861650~5617404084）は、
  同じ期間に 52 リクエスト／16 表示と正常に配信されています。

■ 確認済みの事項
- AndroidManifest の APPLICATION_ID は上記 Android アプリ IDと一致
- Play のパッケージ名と AdMob の登録は一致
- 2つの広告ユニットは Android アプリの配下にある（iOS 側ではない）
- AD_TESTING などテスト設定は本番ビルドでは無効
- 開発者本人の端末は AdMob のテストデバイスに登録済み（広告 ID を更新予定）

■ お願い
Android アプリへの要求が HTTP 403 で拒否されている理由と、
配信を開始するために必要な対応を教えてください。
```

## 返事が来たら

- 内容を仕様書 15-7 の末尾に追記する
- 直すものがコード側にあれば `docs/playtest.html`、設定なら AdMob 側

---

## 投稿先（2026-10-24）

AdMob ヘルプ コミュニティ（個別のメール・チャット窓口は出なかった）
https://support.google.com/admob/thread/474336709
カテゴリ：広告の管理／プラットフォーム：Android

---

## 1通目の返事（2026-10-25・シルバー プロダクト エキスパート＝一般ユーザーのボランティア）

要点：①コミュニティは調査窓口ではない ②「このパブリッシャー ID で収益化・報酬受け取りはあるか」
③Error Code 3 は在庫切れ。リクエストされすぎでマッチしないだけでは。別のプロバイダや種類を。

**こちらの数字と合わないところ：** レポートは Android の**リクエストが 30 日間ゼロ**なので
「リクエストされすぎ」はあり得ない。サーバーの返事は **HTTP 403**（在庫切れの 200 とは別物）。
ユニットはもともとバナー。同じ端末でテスト用ユニットなら表示される。

### 返信（貼る文）

```
Jun KOBAYASHI さん、ありがとうございます。コミュニティの立ち位置、了解しました。

ご質問の件：同じパブリッシャー ID の iOS 版は同期間に 52 リクエスト／16 表示で
収益が発生しています（アカウントは承認済み）。お支払いの基準額には未達なので、
報酬の受け取りはまだありません。

Error Code 3 についてですが、今回は通常の在庫切れとは状況が違うと考えています。
- AdMob のレポート上、Android アプリは過去30日で「リクエスト 0・表示 0」です。
  リクエスト過多でマッチしないのではなく、そもそもリクエストとして記録されていません。
- 端末側のログでは、広告サーバーの応答が HTTP 403 です。在庫切れの場合は
  200 で空の応答が返り、リクエストとして集計されるはずです。
- ユニットは最初からバナーです。同じ端末・同じ構成で Google のテスト用ユニットに
  替えると表示されます。
- アプリは 10/14 に承認済み（メール確認）、ポリシーセンターは問題なしです。

「承認済みのアプリからのリクエストが 403 で拒否される」状況について、
心当たりのある方がいれば教えてください。また、Google の担当者に見てもらえる
経路（お問い合わせ窓口は表示されませんでした）があればご教示ください。
```

### 次の経路：Google Mobile Ads SDK の開発者フォーラム

コミュニティは Google に繋がらない。**技術的な 403 なら、SDK の開発者フォーラムに
Google のエンジニアが返事をする。** 英語。
https://groups.google.com/g/google-admob-ads-sdk

```
Subject: Android: "Ad failed to load: 3" with HTTP 403 for an approved app; test units work

Hi,

Our Android app is approved in AdMob ("Ready" / ad serving enabled, approval e-mail 2026-10-14,
Policy Center: no issues), but every production ad request is rejected and never appears in
AdMob reports (0 requests / 0 impressions over 30 days, 16 installed users).

- Publisher: pub-2313067186861650
- Android App ID: ca-app-pub-2313067186861650~1860567458, package jp.aid.robospeed (live on Google Play since 2026-10-13)
- Banner units (both under the Android app): /8641598226 (result screen), /6921322445 (pause)
- Device: Pixel 9a, Android 17, Google Play services 26.40
- SDK log:  W Ads: Received error HTTP response code: 403  /  I Ads: Ad failed to load : 3
- Same device, same build config, Google test unit (/6300978111) renders fine → SDK/plugin/layout OK.
- The iOS app under the same publisher (~5617404084) serves normally (52 requests / 16 impressions).
- Capacitor + @capacitor-community/admob 8.1.0

Since the server answers 403 rather than a 200 no-fill, and the requests are not counted,
this does not look like inventory. What makes the ad server reject requests from an approved
Android app, and what should we check? Happy to provide a full device log or Ad Inspector output.

Thanks.
```

### もう1つ：Ad Inspector

テストデバイスの広告 ID を今の値に直せば、Play 版のままで **Ad Inspector**（端末を振る／
ジェスチャーで開く）が使え、**なぜ返らなかったかの詳しい理由**がその場で読める。
403 の中身（"App not approved" など）がここに出る可能性がある。登録を直すのが先。

---

## 2通目の返事（2026-10-25）

要点：コミュニティから Google に繋ぐ経路は無い。収益化できていれば AdMob サポート
（https://support.google.com/admob/gethelp）で答えが来るかもしれない。ただし
**アカウントの問題なら答えるが、実装・仕様の問題だと答えないこともある。**
**収益化以前のアカウントには一切答えていないようだ**、とのこと。

**こちらの状況：** 10/24 に gethelp を通ったときは、個別のメール・チャット窓口は出なかった。
報酬の支払い基準額に届いていない（＝まだ一度も支払いを受けていない）のが理由と見られる。
つまり **この経路は、最初の支払いを受けるまで閉じている可能性が高い。**
→ 本命は上の SDK 開発者フォーラム（支払い実績は要らない・Google のエンジニアが答える）。

### 2通目への返信（貼る文）

```
Jun KOBAYASHI さん、ご案内ありがとうございます。

AdMob サポートのお問い合わせページ、もう一度試してみます。
前回開いたときは個別のお問い合わせ窓口が表示されなかったのですが、
「収益化」というのは、お支払い（報酬の受け取り）が一度でもあることを指すのでしょうか。
iOS 版では収益が発生していますが、まだ支払いの基準額には届いていません。

窓口が表示されなかった場合は、Google Mobile Ads SDK のデベロッパー フォーラムでも
聞いてみようと思います。進展があればこちらでも共有します。
```
