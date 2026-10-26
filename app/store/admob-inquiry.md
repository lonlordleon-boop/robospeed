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

### 2通目への返信（貼る文・2026-10-25 に投稿済み）

```
Jun KOBAYASHI さん、ご案内ありがとうございます。

AdMob サポートのお問い合わせページ、もう一度試してみます。
前回開いたときは個別のお問い合わせ窓口が表示されなかったのですが、
「収益化」というのは、お支払い（報酬の受け取り）が一度でもあることを指すのでしょうか。
iOS 版では収益が発生していますが、まだ支払いの基準額には届いていません。

窓口が表示されなかった場合は、Google Mobile Ads SDK のデベロッパー フォーラムでも
聞いてみようと思います。進展があればこちらでも共有します。
```

### gethelp を再挑戦（2026-10-25）

「広告が表示されない」を選んでも、言語を English に替えても、**出るのはコミュニティだけ**。
支払い実績が無いうちは個別窓口は出ない、で確定扱い。→ SDK 開発者フォーラムへ。

---

## SDK の問い合わせフォーム（2026-10-25）

開発者フォーラム（Google グループ）は参加しても「発言する権限がない」で投稿できなかった。
SDK のサポートページ（https://developers.google.com/admob/android/support）の案内は
**「Contact support」＝SDK 専用のフォーム**：https://support.google.com/admob/contact/contact_us_gma_sdk
（英語。gethelp と違い、支払い実績の条件は書かれていない）

| 欄 | 入れる値 |
|---|---|
| Platform | Android |
| Publisher ID | pub-2313067186861650 |
| Google Mobile Ads SDK version | play-services-ads 25.4.x (via @capacitor-community/admob 8.1.0) |
| Device model | Pixel 9a |
| OS version | Android 17 |
| Play / Apple store App ID | jp.aid.robospeed |
| Ad Unit ID | ca-app-pub-2313067186861650/6921322445 |

Subject:
```
Approved Android app: every production ad request gets HTTP 403, 0 requests in reports
```

Issue description:
```
Our Android app (jp.aid.robospeed, live on Google Play since 2026-10-13) is approved in AdMob
("Ready" / ad serving enabled, approval e-mail 2026-10-14; Policy Center: no issues), but no
production ads are ever served. AdMob reports show 0 requests / 0 impressions for the Android
app over the last 30 days, while about 16 users have installed it.

On the device, every production request fails:
  W Ads: Received error HTTP response code: 403
  I Ads: Ad failed to load : 3

With the same build configuration on the same device, the Google test banner unit
(ca-app-pub-3940256099942544/6300978111) loads and renders fine, so the SDK, plugin and
layout are working. The iOS app under the same publisher (ca-app-pub-2313067186861650~5617404084)
serves normally (52 requests / 16 impressions in the same period).

Android App ID: ca-app-pub-2313067186861650~1860567458
Banner units (both under the Android app): /6921322445 (pause screen), /8641598226 (result screen)
app-ads.txt is published at https://aidgames.jp/app-ads.txt and verified.

Since the server answers 403 instead of a 200 no-fill, and the requests are not counted in
reports, this does not look like a lack of inventory. Could you check why the ad server rejects
requests from this approved Android app?
```

Steps to reproduce:
```
1. Install ROBO SPEED (jp.aid.robospeed) 1.0.10 from Google Play on an Android device.
2. Start a game and open the pause screen (or finish a run to reach the result screen).
3. The app requests a banner from ca-app-pub-2313067186861650/6921322445 (or /8641598226).
4. logcat shows "Received error HTTP response code: 403" and "Ad failed to load : 3";
   no ad is displayed and the request does not appear in AdMob reports.
```

Did you attempt to reproduce with examples? → No（サンプルアプリでは試していない）
Did you attempt to reproduce with test ad unit IDs? → Yes, test ads work（テスト用ユニットでは出る）
Priority → 3つのうち「本番で広告が出ない」に一番近いもの

**2026-10-25 に送信済み（チケット ID 0-1354000042036）。** 返事の目安は2営業日（10/27 火ごろ）。 選んだもの：サンプル＝試みなかった／テスト広告ユニット＝再現できなかった（テストなら出る）／
優先度＝技術的なトラブルシューティングとサービスに関する質問。添付・共有なし。返事待ち。

---

## 追加で分かったこと（2026-10-26）— 返事が来たら付け足す

1. **iPhone 版は配信されている。** 2026-10-25 20:00 に「広告の配信が始まりました」のメール。レポートに出たのは iPhone だけ
2. **配った AAB の中のアプリIDは正しい。** 1.0.10 の AAB の `base/manifest/AndroidManifest.xml` を直接読んで、
   `ca-app-pub-2313067186861650~1860567458` を確かめた
3. **別の人の Android でも同じ。** 友達の端末（楽天モバイル回線・**5年ほど前の端末**・Play 版・版の表示は最新の 1.0.10。機種名は未確認）の一時停止と結果画面で、
   広告のぶんのすき間（AdMob の準備が済んで、頼む直前に空く）があるのに、広告が出ない。
   → 開発者の端末だけの問題ではない。頼みには行けているが、返ってこない。
   新しい Pixel 9a と5年前の端末の両方で同じなので、端末の新しさにも関係ない
4. **まだ見ていないもの：** 10/26・10/27 の Android のリクエスト数（友達が遊んだ日。日付は 26 か 27 の未明）

### 返事への付け足し（英文・チケット 0-1354000042036 に返信するとき）

```
Additional information:

1. The iOS app under the same publisher started serving on 2026-10-25 (we received the
   "ads are now serving" e-mail), so the account, payments and app-ads.txt are fine.
   Only the Android app is affected.

2. We extracted the AndroidManifest from the exact AAB uploaded to Google Play (1.0.10)
   and confirmed the App ID is ca-app-pub-2313067186861650~1860567458.

3. The issue is not limited to the developer's device. On another user's Android device
   (about 5 years old, different carrier, Play Store install, latest version 1.0.10), the app initializes the SDK and requests the
   banner (the layout reserves the banner space only after MobileAds initialization
   succeeds), but no ad is returned. Same result as on our Pixel 9a (HTTP 403 / error 3),
   so it happens on both a recent and an older device.

Ad requests from this device on 2026-10-26/27 (JST, around 00:30) should exist, but the
Android app still shows no rows in AdMob reports.
```

> 4 のレポートを見て、10/26・27 も Android が 0 だったら、最後の段落はそのまま使う。
> 数字が出ていたら、最後の段落を「the requests now appear in reports (N requests, 0 impressions)」に書き換える。

---

## SDK サポートの返事（2026-10-26・ケース 00491339・Sellside Support の Vamshi）

**原因が分かった。** Android の2つのユニット（`/6921322445`・`/8641598226`）は
**「Partner Bidding（パートナー入札）」のユニットとして作られていて、「Standard（通常）」ではない。**
パートナー入札のユニットは、Google が**よそのメディエーションの入札に参加するため**のもので、
アプリの SDK から直接頼まれると、**サーバーが仕様どおり HTTP 403 で断る。**
（リクエストとして集計されないのもこのため）

直しかた：AdMob の「広告ユニット」タブで **Standard の広告ユニットを新しく作り**、その ID をアプリに入れてビルドし直す。
案内：「Ad units, ad formats, and ad types」のヘルプ記事。

iOS のユニット（`/2991240743`・`/9476013186`）は配信されているので、こちらは通常のユニットのはず。
