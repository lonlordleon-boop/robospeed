# ROBO SPEED iPhone 版の手順（Mac で使う）

2026-10-19 に Windows 側で書いた。**Mac の Claude はこれを最初に読むこと。**

---

## 0. 作業の決まり（本人との約束）

- **返事・説明はすべて日本語。** 本人は Mac に慣れていない。キーボードは Windows 用（`~` `*` `_` が打ちにくい）
- **ファイルを勝手に消さない。** 既存のコードを大きく削らない。日本語のコメントは消さない・英語にしない
- **新しいパッケージを勝手に入れない。** `package.json` に書いてあるものを `npm install` で入れるのは良い。それ以外は聞く
- **パスワード・確認コードは本人に入力してもらう。** Apple ID でのログインは本人が操作する
- **1つずつ進める。** 終わったら実物（画面・ファイル）で確かめてから次へ
- 本人は**本名を出したくない**（珍しい名前）。作る文やページに本名を書かない

---

## 1. いまの状態（Windows 側で済んだこと）

| 項目 | 値・状態 |
|---|---|
| バンドルID | `jp.aid.robospeed`（Apple の Identifiers に登録済み） |
| Team ID | `35N4AM2XQ7` |
| App Store Connect | 「ROBO SPEED」を作成済み。Apple ID（アプリの番号）は `6824338951`、SKU は `robospeed-ios` |
| AdMob の iOS アプリID | `ca-app-pub-2313067186861650~5617404084` |
| AdMob の広告ユニット | 結果画面 `…/2991240743`、一時停止 `…/9476013186`（**`docs/playtest.html` に入れ済み**） |
| ゲームの中の切り替え | iPhone のときだけ、広告の番号・お知らせの「App Store で更新する」・図鑑の保存先の説明が変わる（`platform()`） |
| アイコン | `app/store/ios_icon_1024.png`（1024×1024・透明なし。Android と同じ絵） |
| `@capacitor/ios` | `app/package.json` に入っている（8.5.2） |
| `app/ios` | **git に入っていない**（Mac で作るもの。`.gitignore` の対象） |

**Android 版は Google Play で公開中（1.0.8）。** 同じ `docs/playtest.html` から作るので、ゲームの中身は Android と同じ。

---

## 2. 組み立ての流れ（Android と同じ3段＋1）

```
docs/playtest.html
   ↓ ① node build-www.mjs           （app フォルダの中で）
app/www/
   ↓ ② npx cap sync ios             ← iOS は copy ではなく sync（プラグインも入れ直す）
app/ios/App/App/public/
   ↓ ③ Xcode で組み立てる
   ↓ ④ 実機で、タイトル左下の版の表示が docs/playtest.html の BUILD と同じか見る
```

**② を飛ばすと、古い中身のまま出る。** Android で実際にやってしまった（仕様書 15-12）。
ビルドが成功しても中身が古いことがある。**必ず実機で版の表示を見る。**

---

## 3. 最初の1回だけやること

### 3-1. 最新を取ってくる

```bash
cd ~/robospeed      # リポジトリの場所（違えば本人に聞く）
git pull
cd app
npm install
```

### 3-2. iOS のプロジェクトがあるか

`app/ios` が**無ければ**作る。**あれば作り直さない**（手で直した設定が消える）。

```bash
ls ios || npx cap add ios
```

### 3-3. 中身を入れる

```bash
node build-www.mjs
npx cap sync ios
```

`build-www.mjs` の最後に「見つからない ○ 件」と出たら止まる。**0 件でないと絵や音が欠ける。**

### 3-4. Info.plist に足すもの

場所：`app/ios/App/App/Info.plist`

| キー | 値 | なぜ |
|---|---|---|
| `GADApplicationIdentifier` | `ca-app-pub-2313067186861650~5617404084` | **無いと起動直後に落ちる。** Android の AndroidManifest の APPLICATION_ID に当たる |
| `SKAdNetworkItems` | Google の案内どおりの一覧（最低 `cstr6suwn9.skadnetwork`） | 広告の効果測定。無くても動くが、広告の値が下がる |
| `ITSAppUsesNonExemptEncryption` | `NO`（Boolean） | 暗号は HTTPS だけ。毎回の「輸出の質問」を省ける |
| `CFBundleDisplayName` | `ROBO SPEED` | ホーム画面に出る名前 |

**`NSUserTrackingUsageDescription`（追跡の許可を聞く画面）は、まず入れない。**
入れると「追跡を許可しますか」を出す作りが要る。出さなければ広告は「本人に合わせない広告」になるだけで、出ることは出る。

### 3-5. Xcode の設定

```bash
npx cap open ios
```

App の TARGETS →

| タブ | 設定 |
|---|---|
| Signing & Capabilities | **Automatically manage signing** にチェック、Team は本人のチーム（`35N4AM2XQ7`） |
| General → Identity | Bundle Identifier `jp.aid.robospeed`、Version は `1.0.9`（Android と合わせる）、Build は `1`（上げるたびに +1） |
| General → Supported Destinations | **iPhone だけ**にする（iPad を外す）。iPad を残すと iPad の画面写真まで求められる |
| General → Deployment Info | 画面の向きは **Portrait だけ**（Android も縦固定） |
| Assets → AppIcon | `app/store/ios_icon_1024.png` を 1024 の枠に入れる |

App Store Connect のバージョンは「1.0」で作られている。**Xcode の Version と同じ数字にそろえる**（App Store Connect の画面で 1.0 → 1.0.9 に直す）。

---

## 4. 本人の iPhone で動かす

1. iPhone を Mac に USB でつなぐ。iPhone に「このコンピュータを信頼しますか」→ 信頼
2. iPhone の「設定」→「プライバシーとセキュリティ」→ **デベロッパモード** をオン（再起動が要る）
3. Xcode の上の段で、つないだ iPhone を選んで ▶（Run）

### 確かめること

| 見るところ | 正しい状態 |
|---|---|
| タイトル左下の版の表示 | `docs/playtest.html` の `BUILD` の日付と同じ |
| 音 | 効果音・BGM・ほめ言葉の声が鳴る。**iPhone の横の消音スイッチがオンだと鳴らないことがある**（WebView の決まり）。まずスイッチを確かめる |
| 画面の上下 | 時計・電池の下や、下の線（ホームバー）に文字やボタンが潜っていない |
| ランキング | 登録できる。順位表が出る |
| 名前の入力 | キーボードに入力欄が隠れない（Android で一度あった・仕様書 15-10） |
| 図鑑の保存先の説明 | 「記録はこの端末に保存されます。アプリを削除すると失われます。」 |
| 広告 | 結果画面と一時停止で上に出る（出なくても、すぐは「在庫なし」のことがある・下を見る） |

### 広告を確かめるとき（大事）

**本人の iPhone で本物の広告を押させない。** アカウントが止められることがある。

Xcode の下のログに、次のような行が出る：

```
<Google> To get test ads on this device, set: ... testDeviceIdentifiers = @[ @"xxxxxxxx" ]
```

この `xxxxxxxx` を、本人に AdMob の「設定」→「テストデバイス」に **プラットフォーム iOS** で登録してもらう。
登録が効くと、その iPhone には「Test Ad」と書かれた広告が出る。

ログに `Ad failed to load : 1` などが出たら、番号を確かめる。
`: 3` は「在庫なし」で、アプリの作りは正しい（Android の公開直後もこれだった）。

---

## 5. App Store に出す

1. Xcode：上の段の行き先を **Any iOS Device (arm64)** にする → Product → **Archive**
2. できたら Organizer が開く → **Distribute App** → **App Store Connect** → Upload
3. App Store Connect の **TestFlight** に数十分で出てくる。本人の iPhone で TestFlight アプリから入れて、もう一度4の確かめをする
4. App Store Connect で掲載情報を埋める（説明文・画面写真・年齢区分・プライバシー）。**文は Windows 側の Claude が用意する**（`app/store/listing.md` の Android 用を元に）
5. 審査に提出

### 気をつけること

- **配信する国は日本だけ。** EU に出すと、デベロッパの住所と電話番号の公開を求められる（本人は出したくない）
- **画面写真は iPhone の大きいサイズ（6.9 インチ・1320×2868 など）が要る。** 本人の iPhone で撮る
- App Store Connect に「**使用許諾契約に同意を**」の黄色い知らせが出ていたら、提出の前に消えているか確かめる（2026-10-19 時点でまだ出ていた）
- アップロード時に「プライバシーマニフェスト」の警告（ITMS-91053 など）が出たら、内容を見て本人に相談

---

## 6. あとで中身を直したとき

```bash
cd ~/robospeed && git pull
cd app
node build-www.mjs
npx cap sync ios
```

Xcode で **Build を +1** して Archive → Upload。
`docs/playtest.html` を直すのは Windows 側でも Mac 側でもよいが、**同時に両方で直さない**（git でぶつかる）。

---

## 7. 終わったら

- Mac で直したもの（`app/ios` は git に入らない）の中で、**手で書き足した設定**（Info.plist など）は、ここの手順書に書き足しておく。Mac が壊れたときに作り直せるように
- 仕様書 `docs/GAME_SPEC.md` の 15-13 に、やったことと分かったことを足す

---

## 8. Mac で手で入れた設定（2026-10-19 の記録）

`app/ios` は git に入らないので、**Mac が壊れたら全部消える。** 作り直すときは、ここに書いたとおりに入れ直す。
リポジトリの場所は `~/Documents/robospeed`（3-1 の `~/robospeed` とは違った）。
`app/ios` は 2026-09-24 に作られたものがすでにあったので、作り直していない。

### 8-1. Info.plist（`app/ios/App/App/Info.plist`）

| キー | 入れた値 | メモ |
|---|---|---|
| `GADApplicationIdentifier` | `ca-app-pub-2313067186861650~5617404084` | 新しく足した |
| `SKAdNetworkItems` | `cstr6suwn9.skadnetwork` の1件だけ | 新しく足した。Google の案内の全部はまだ入れていない |
| `ITSAppUsesNonExemptEncryption` | `NO`（Boolean） | 新しく足した |
| `CFBundleDisplayName` | `ROBO SPEED` | **最初から入っていた**（`npx cap add ios` が入れる） |
| `UISupportedInterfaceOrientations` | `UIInterfaceOrientationPortrait` の1つだけ | 横向き2つを消した（縦固定） |

さわっていないもの：
- `NSUserTrackingUsageDescription` は入れていない（3-4 のとおり）
- `UISupportedInterfaceOrientations~ipad` は残したまま（iPhone だけにしたので使われない）
- `UIRequiredDeviceCapabilities` の `armv7` は、Capacitor が作ったまま残してある。アップロードで何か言われたら、ここを `arm64` にする

入れ直すときは、`app/ios/App/App` の中で次を打てば同じになる（Xcode の画面で入れてもよい）：

```bash
/usr/libexec/PlistBuddy -c "Add :GADApplicationIdentifier string ca-app-pub-2313067186861650~5617404084" Info.plist
/usr/libexec/PlistBuddy -c "Add :SKAdNetworkItems array" -c "Add :SKAdNetworkItems:0 dict" -c "Add :SKAdNetworkItems:0:SKAdNetworkIdentifier string cstr6suwn9.skadnetwork" Info.plist
/usr/libexec/PlistBuddy -c "Add :ITSAppUsesNonExemptEncryption bool false" Info.plist
/usr/libexec/PlistBuddy -c "Delete :UISupportedInterfaceOrientations" -c "Add :UISupportedInterfaceOrientations array" -c "Add :UISupportedInterfaceOrientations:0 string UIInterfaceOrientationPortrait" Info.plist
```

### 8-2. Xcode の設定（`app/ios/App/App.xcodeproj/project.pbxproj`）

Debug と Release の両方に入っている。Xcode の画面（3-5）で入れるのと同じ中身。

| 設定 | 値 | メモ |
|---|---|---|
| `DEVELOPMENT_TEAM` | `35N4AM2XQ7` | 新しく足した（Signing の Team） |
| `CODE_SIGN_STYLE` | `Automatic` | 最初から |
| `PRODUCT_BUNDLE_IDENTIFIER` | `jp.aid.robospeed` | 最初から |
| `MARKETING_VERSION` | `1.0.9` | `1.0` → `1.0.8` → `1.0.9`（2026-10-20・Android の 1.0.9 に合わせた） |
| `CURRENT_PROJECT_VERSION` | `1` | 最初から（Build。上げるたびに +1） |
| `TARGETED_DEVICE_FAMILY` | `1` | `"1,2"` から直した（iPhone だけ。iPad を外した） |

### 8-3. アイコン

`app/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png` を、
`app/store/ios_icon_1024.png` で上書きした（最初は Capacitor の青い「×」の仮の絵だった）。ファイル名はそのまま。

### 8-4. 実機で動かすまでにつまずいたところ

- **Xcode に Apple ID を入れる場所：** Xcode 27 では「Xcode」→「Settings…」→「**Apple Accounts**」→ 右の「**Sign In…**」。左下の「＋」は無い
- 🍎 の右が「Claude」のままだと、Xcode のメニューが出ない。Dock の青い金づちを押して Xcode を前に出す
- **デベロッパモードは、オン → 再起動 → 「オンにする」を押してパスコード** まで済ませないと効かない
- 初めての iPhone は、開発者アカウントへの登録が要る。Xcode の ▶ なら自動。コマンドで組み立てるときは `-allowProvisioningDeviceRegistration` を付ける
- シミュレータは「CoreSimulator is out of date」で使えなかった（実機には関係ない）

コマンドで組み立てて iPhone に入れるとき（Xcode の ▶ と同じ）：

```bash
cd ~/Documents/robospeed/app/ios/App
xcrun devicectl list devices
xcodebuild -project App.xcodeproj -scheme App -configuration Debug -destination 'id=<iPhone の番号>' -derivedDataPath /tmp/rsdd -allowProvisioningUpdates -allowProvisioningDeviceRegistration build
xcrun devicectl device install app --device <iPhone の番号> /tmp/rsdd/Build/Products/Debug-iphoneos/App.app
xcrun devicectl device process launch --terminate-existing --device <iPhone の番号> jp.aid.robospeed
```

`<iPhone の番号>` は、`xcrun devicectl list devices` で出る Identifier。

### 8-5. 実機で分かったこと

- **音が出ないときは、まず消音モード。** 効果音・BGM・ほめ言葉の声は全部 Web Audio で鳴らしていて、iPhone では消音モードのとき Web Audio は鳴らない（動画の音は鳴る）。iPhone 16 は消音スイッチが無く、アクションボタンかコントロールセンターの🔔で切り替わる。**消音中でも鳴らすかどうかは、まだ決めていない**（鳴らすようにすると、ゲーム中はほかのアプリの音楽が止まる）
- **作業台の部品が原寸で描かれて、はみ出した。** WebKit の作りの違い。`docs/playtest.html` を直して main に入れた（BUILD `2026-10-19a`）
- **Mac で iPhone と同じ見た目を確かめられる。** Mac の WKWebView は iPhone と同じ WebKit。作業台の崩れは Mac でも同じように出た
