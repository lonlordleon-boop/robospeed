using System;

namespace RoboSpeed.Core
{
    /// <summary>
    /// 調整値をすべてここに集める。仕様書 12-3。
    /// 自動対戦はこの値を振って回すので、他のファイルに数値を直接書かないこと。
    /// 既定値はすべて「仮」であり、実測で決める。
    /// </summary>
    public class Balance
    {
        // ---- 役の倍率（仕様書 4-1）。攻撃と防御の両方に使う ----
        // 倍率の幅は、組み立て時間の幅に合わせる。
        //
        // 実測（対戦の中で計測）では、組み立て時間は
        //   ワンペア 8.0秒 → ピュアカラー 13.1秒 の 1.6倍しか伸びない。
        // ここに 1.0〜7.0（7倍）の倍率を乗せると、粘る打ち手が一方的に強くなり、
        // ピュアカラー狙いが速攻に 95% 勝ってしまった。
        //
        // 一度 8秒で見切る役狙いボットで測ったときは拮抗して見えたが、
        // 最後まで粘る打ち手を入れると破綻した。**測る道具のほうが甘かった。**
        public double[] HandMultiplier =
        {
            1.00, // OnePair      38.40%
            1.11, // TwoPair      28.80%
            1.26, // ThreeOfAKind 19.20%
            1.53, // FullHouse     6.40%
            1.53, // Prism         3.84%（フルハウスと同格。差は必殺技が5つ使えること）
            1.75, // FourOfAKind   3.20%
            2.50, // PureColor     0.16%
        };

        // ---- 本拠地ゲージ（仕様書 6-1）----
        /// <summary>
        /// 初期耐久。1発の平均ダメージを100前後とみて置いた仮値。
        /// 1400 → 1500 ★v1.10（実機で決めた。docs/playtest.html の SPEC.baseHp と同じ値）
        /// </summary>
        public double BaseHp = 1500.0;
        /// <summary>試合の制限時間。</summary>
        public int MatchLimitMs = 180000;

        /// <summary>
        /// 役倍率の傾き。上の表を 1 + (表の値 - 1) × MulScale で使う。
        ///
        /// ---- 戦術を分ける値ではなかった（仕様書 9-6e）----
        ///
        /// 長らく「速攻と役狙いを釣り合わせる値」として扱ってきたが、
        /// テトリス型の走りで測り直すと **2.5倍から6.0倍まで振っても
        /// 撃破数は 5.9〜6.6機 の間にしか動かない**。
        ///
        /// 走りの中では、粘っても役を上げても撃破数はほぼ変わらないため、
        /// **この値が決めているのは戦略ではなく「大きい一撃の気持ちよさ」**。
        /// したがって実測ではなく **実機の手触りで決める値**。
        ///
        /// ---- 3.0 → 7.0 ★v1.10（仕様書 9-6h）----
        ///
        /// 上の「戦略を分けない」という結論は **持ち越しが無い前提** のものだった。
        /// 余ったダメージを捨てている限り、倍率を上げても捨てる量が増えるだけで、
        /// どう振っても「2ペアで速く撃つ」が最良になる。
        ///
        /// **CarryOverKill と EnemyHp 600 と組み合わせて初めて効く。**
        /// 3つそろうと、狙いを上げるほど撃破数が伸びる形になる：
        ///   速攻 16.7 → 2ペア 19.0 → 4カード 19.8（各200本）
        ///
        /// このとき役の帯はこうなる（基礎威力 95〜115）。
        ///   ワンペア   95〜 115 / ツーペア  168〜 203 / スリーカード 268〜 324
        ///   フルハウス 447〜 541（プリズム 519はこの中）
        ///   フォーカード 594〜 719 / ピュアカラー 1092〜1322
        ///
        /// **下限は 2.0。** それ未満だと基礎威力の幅（1.21倍）が帯を食い破る。
        /// </summary>
        public double MulScale = 7.0;

        public double MultiplierOfScaled(Hand hand)
        {
            return 1.0 + (HandMultiplier[(int)hand] - 1.0) * MulScale;
        }

        // ---- 時間コスト（仕様書 3-3／3-6／6-4）----
        /// <summary>カードを1枚装着するまで。指を動かす時間。</summary>
        public int FlickMs = 400;

        /// <summary>
        /// ボットが1手ごとに置く「考える時間」。すべての行動に加算される。
        ///
        /// これが 0 だと、ボットは 400ms×5枚 = **2秒で1体** 組んでしまう。
        /// 実機の人間は 11〜14秒（9-5g）。**この差を入れずに測ると、
        /// 速さの軸だけが極端に効いて、役を狙う戦術が実際よりずっと弱く出る。**
        ///
        /// テトリス型の走りでは、これが段階的に詰まっていくものにあたる（9-6b）。
        /// </summary>
        public int BotLagMs = 900;
        /// <summary>
        /// パージ（手札4枚をまとめて捨てて引き直す）の対価。仕様書 3-3／9-5r。
        /// 単独の引き直しは v1.10 で廃止した。狙った1枚を同じ手軽さで捨てられると、
        /// まとめ買いとしてのパージを使う理由が無くなるため。
        /// </summary>
        public int PurgeMs = 800;
        /// <summary>上書きのロック。役を買う対価。</summary>
        public int OverwriteLockMs = 700;

        /// <summary>
        /// 1機あたりの上書き回数の上限。0 なら無制限。
        /// 機体が全損して組み直すたびに 0 に戻る。
        ///
        /// 上書きの対価を「時間」だけで払わせると、粘れば粘るほど役が上がるため、
        /// 待つ側に有利が寄る。回数で頭打ちにすると、
        /// 「あと何回直せるか」という別の判断が生まれ、いずれ撃たざるを得なくなる。
        /// </summary>
        public int MaxOverwritesPerBuild = 0;

        // ---- 攻撃まわり（仕様書 6-4）----
        /// <summary>攻撃演出。両者停止するので勝敗には効かない。見せ場のみ。</summary>
        // 実機で「演出でチョット休める感じが望ましい。役が強いほどド派手に」。
        // 200msは瞬きで休めない。下を350msに上げ、上を4000msまで伸ばした。
        // 両者が止まるので勝敗には効かない。純粋に見せ場と息継ぎ。
        public int[] EffectMs = { 350, 400, 700, 1000, 2200, 2200, 6000 };
        /// <summary>
        /// 装填時間。出撃側だけが動けない＝無防備な時間。
        /// 仕様書 6-4 は「強い役ほど長い」としていたが、自動対戦の結果それは逆だった。
        /// 速攻が強すぎる構造なので、ブレーキは弱い攻撃の連打側に置く。
        /// 良い機体はよく殴り、よく耐え、立ち直りも速い＝役が機体の質そのものになる。
        /// </summary>
        public int[] ReloadMs = { 1600, 1400, 1100, 800, 700, 600, 400 };

        /// <summary>
        /// 倒しきって余ったダメージを、次の機体に持ち越すか。
        ///
        /// **持ち越さないと、上限を超えた分は捨てられる。**
        /// 敵の耐久 600 に対しピュアカラーは 1092〜1322 出るので、
        /// 捨てる設計では **半分以上を捨てていた。**
        /// 捨てられる限り「強い役を狙う」ことに見返りが出ず、
        /// 測定ではどの倍率・どの耐久でも「2ペアで撃つ」が最良だった（仕様書 9-6h）。
        ///
        /// **1発で2機まとめて落ちることがある。** 呼び出し側は while で回すこと。
        /// </summary>
        public bool CarryOverKill = true;

        /// <summary>
        /// 当たった攻撃が相手の部位をいくつ壊すか。
        /// 妨害（相手の作業台へ送る）を廃止した代わりに、
        /// 相手を後退させる役目はここが全部引き受ける。仕様書 9-5f。
        /// 拡散弾のように元から壊す技は、これの2倍を壊す。
        /// </summary>
        public int StripOnHit = 1;

        /// <summary>
        /// 部位破壊が起きる確率。1.0 なら当たれば必ず壊す。
        ///
        /// ---- 0.25 から 1.0 に戻した経緯（仕様書 9-6e）----
        ///
        /// v1.8 で 0.25 にした。理由は「毎回壊すと、組むのに時間をかける打ち手が
        /// 一方的に潰れる」で、1v1 の実測（破壊なし 60% / 毎回破壊 9%）が根拠だった。
        ///
        /// **その測定の前提が間違っていた。**
        /// 1v1 は「最後まで粘る打ち手」どうしの決着1回の勝負で、
        /// 実際のゲーム（テトリス型の走り）とは別物。
        /// 走りの中で測り直すと、**最良の粘りは1〜2秒**しかなく、
        /// 破壊率の差はほとんど出ない。
        ///
        ///   破壊 25%  … 6.4機   破壊 100% … 6.2機
        ///
        /// **破壊が支配的に見えたのは、粘る打ち手だけを見ていたから。**
        ///
        /// プロトタイプは一度も 0.25 を入れておらず、実機で「アリ」と評価された
        /// 手触りは 100% のほう。**触って良かった側に合わせる。**
        /// </summary>
        public double StripChance = 1.0;

        // ---- 副色の効果（仕様書 9-5n）----

        /// <summary>
        /// 副色の効果の強さ。0 なら副色は無効＝v1.8 までと同じ挙動。
        ///
        /// 効果量は「副色の基礎威力 × この値」。1.0 なら 95〜115 相当。
        /// 役倍率は **掛けない**。掛けると強い役ほど副次効果まで伸びて、
        /// 「困ったときの道具」ではなく「勝っている側がさらに勝つ装置」になる。
        ///
        /// ---- 既定を 0（無効）にしてある理由 ----
        ///
        /// 実測の結論は「**副色に無料の形は無い**」だった。
        ///   ・ダメージを混ぜる  → 役の階段が壊れる（SubColorMix の注を参照）
        ///   ・回復やシールドにする → **試合が伸びる**（傾き2.2・0.5x で 90.1秒 → 101.7秒）
        /// シールドだけに限っても 100.0秒 で、伸びかたはほぼ同じだった。
        /// つまり原因は回復ではなく「**攻撃以外に価値を回すこと**」そのもの。
        ///
        /// しかも副色はバランスの是正には **ならない**。0x の時点で 46.0% と
        /// すでに釣り合っているので、入れるなら傾きを下げて相殺する必要がある。
        /// 採用は「選択肢が増える楽しさ」と「試合が13%伸びる」の取引で決める。
        ///
        /// 注意：ボットは副色を **狙っていない**。人間が狙えば発生率も効果も上がるので、
        /// ここの数字は **下限** として読むこと。
        /// </summary>
        public double SubColorScale = 0.0;

        /// <summary>
        /// 副色1つぶんの価値を、追加ダメージ／回復／シールドにどう配るか。
        /// 行がメーカー（赤・青・黄・緑・紫）、列が [攻撃, 回復, シールド]。
        ///
        /// **合計は必ず 1.0。** 足し算にすると副色が付いた役が一方的に強くなり、
        /// せっかく揃えた役の階段（9-5m）がまた歪む。
        /// 総量は変えず、**形だけ選べる**ようにする。
        ///
        /// ---- 攻撃の列を全部 0 にした理由 ----
        ///
        /// 当初案は「赤＝追加ダメージ」だったが、**必ず階段を壊す**ことが分かった。
        /// 傾き2.2 のとき ツーペアの帯は 118〜143、スリーカードは 149〜181 で、
        /// 境目の余裕は 6 しかない。副色0.5x でも赤なら +57.5 が乗るので、
        /// ツーペアが 175〜200 になってスリーカードを丸ごと飛び越える。
        ///
        /// **ダメージは役の階段そのものの軸なので、副色から触ってはいけない。**
        /// 色の差は「回復」と「シールド」の配分だけで出す。
        /// </summary>
        public double[,] SubColorMix =
        {
            { 0.0, 0.0, 1.0 },   // 赤   … シールド
            { 0.0, 1.0, 0.0 },   // 青   … 回復
            { 0.0, 0.5, 0.5 },   // 黄   … 半々
            { 0.0, 0.3, 0.7 },   // 緑   … シールド寄り
            { 0.0, 0.7, 0.3 },   // 紫   … 回復寄り
        };

        /// <summary>
        /// シールドの持続。次の一撃を受けるまで持つが、永久には残さない。
        /// </summary>
        public int ShieldLifeMs = 12000;

        // ---- ガード（仕様書 6-2b／6-2d）----
        /// <summary>削り係数。最も敏感な数値。亀化するかを決める。</summary>
        public double GuardCoefficient = 0.10;
        /// <summary>ガード解除後の硬直。ガードからの即時反撃を防ぐ。</summary>
        public int GuardReleaseLagMs = 700;
        /// <summary>
        /// ガードに完成した機体を要求するか。
        /// 未完成でも受けられると、組みかけを捨てるだけで大技を防げてしまい、
        /// ガードが安すぎる。完成必須にすると1回のガードが機体1機分の対価になる。
        /// </summary>
        public bool GuardRequiresComplete = true;

        // ---- 背水（仕様書 6-5）----
        public double DesperationThreshold = 0.30;
        public double DesperationMultiplier = 1.30;

        // ---- カードの供給（仕様書 3-2）----
        public int SupplyLineSize = 4;

        /// <summary>
        /// 各自が自分の4枚と自分の山札を持つか。仕様書 9-5c。
        ///
        /// 共有ライン（中央の4枚を取り合う）は実機で却下された。
        /// 「スピードというよりも百人一首みたいになってる」
        /// 「ドラッグしてても取られるのはモヤっとする」
        /// トランプのスピードは元々**手札が各自4枚の私有**で、
        /// 共有の場から札を奪い合うのは、かるたの構造だった。
        /// </summary>
        public bool PrivateLines = true;

        /// <summary>
        /// 各カードを何枚ずつ入れるか。私有なら1枚ずつ（各自25枚）で足りる。
        ///
        /// 共有ラインだった頃は、1色あたり5枚しか無いために
        /// 両者が同じ色を取り合って膠着した（時間切れ 50〜68%）ので 2枚ずつにしていた。
        /// **取り合いが無ければ、その枯渇は起きない。**
        /// </summary>
        public int DeckCopies = 1;

        public int DeckSize { get { return Counts.Manufacturers * Counts.Slots * DeckCopies; } }

        /// <summary>
        /// 山札を持たず、毎回その場で1枚を等確率で湧かせるか。
        /// 決着は本拠地ゲージのみなので、供給が尽きて試合が止まることは無い。
        /// </summary>
        public bool InfiniteSupply = false;

        // ---- テトリス型の走り（仕様書 9-6）----
        /// <summary>
        /// ステージで区切らず、1本の走りの中で相手がだんだん速くなる方式。
        /// 序盤は役を狙う余裕があり、終盤は速さ勝負になる。負けたら終わり。
        /// </summary>
        public bool Endless = true;
        /// <summary>走り出しの相手の「考える時間」。組み立て 12.0秒 に相当。</summary>
        public int StartLagMs = 2000;
        /// <summary>
        /// 行き着く先。組み立て **3.5秒** に相当。
        ///
        /// 500ms（4.5秒）だと 7機目で加速が止まり、そこから先は平地になる。
        /// 実測では平地が走り全体の **18%** を占めていた。300ms にすると **6%** まで落ち、
        /// 走りの長さ（332秒→316秒）と撃破数（7.7→7.3）はほぼ変わらない。仕様書 9-6d。
        ///
        /// 敵HPの増加や回復の減衰でも平地は潰せるが、どちらも撃破数を 5〜6機 に下げる。
        /// **表示される「8機撃破」が「6機」に減るのは、得点が下がったようにしか見えない。**
        /// </summary>
        public int FloorLagMs = 300;
        /// <summary>
        /// 1機倒すごとに詰める量。時間で連続的に詰めていたら
        /// 実機で「加速には気づかなかった」と出た。**段で上げる。** 仕様書 9-6b3。
        ///
        /// 220 → 140 → 80 ★v1.10。試遊で「20機は簡単に行けるように」と出た（9-6g）。
        /// 下限に達するのは 8機目 → 13機目 → **22機目**。
        /// </summary>
        public int StepLagMs = 80;
        /// <summary>
        /// 相手1機の耐久。自分と同じだと1機に2分かかり、節目が来なさすぎる。
        /// 700 → 420 ★v1.10。節目の間隔を詰めて撃破数を伸ばした（9-6g）。
        /// </summary>
        public double EnemyHp = 600.0;
        /// <summary>1機倒すごとに戻る本拠地ゲージ（割合）。</summary>
        /// 0.35 → 0.45 ★v1.10（9-6g）。粘れるようにして撃破数を伸ばした。
        public double HealOnKill = 0.45;

        /// <summary>1本の走りの上限。これに当たったら「終わらない設計」になっている。</summary>
        public int EndlessLimitMs = 900000;

        /// <summary>
        /// 相手の速さが下限に達したあとも走りを締め続けるための、第2・第3の軸。
        ///
        /// 速さだけで締めると **下限で加速が止まり、そこから先は平地** になる。
        /// テトリスは最後まで圧が増え続けるので、そこが構造として違う。
        /// 実機では7〜8機で下限（4.5秒）に到達していた。仕様書 9-6d。
        /// </summary>
        /// <summary>1機倒すごとに相手の耐久が増える量。0 なら従来どおり一定。</summary>
        /// 0 → 10 → **7** ★v1.12i（仕様書 9-6r）。playtest.html と同じ値にしてある。
        /// **ここを実機とずらすと、測定が別のゲームを測ることになる**（9-2d の轍）。
        public double EnemyHpGrowth = 7.0;
        /// <summary>1機倒すごとに、撃破時の回復にかかる減衰。1.0 なら減らない。</summary>
        /// 1.0 → **0.995** ★v1.12f（9-6r）。playtest.html の healDecay と同じ。
        public double HealDecay = 0.995;
        /// <summary>回復がここより下には落ちない。</summary>
        public double HealFloor = 0.05;

        /// <summary>
        /// 壁の先の「二段目の坂」。仕様書 9-6o の案A。★v1.12d
        ///
        /// 下限（FloorLagMs）に達すると、相手はそこから先 **二度と速くならない。**
        /// 速い打ち手はそこで詰まなくなり、走りが飽きるまで終わらなくなる
        /// （実機でイージー92機）。この機数を過ぎたら、また少しずつ詰め始める。
        ///
        /// **既定は 0 で効かない。** 入れる／入れないを測ってから決めるための軸。
        /// </summary>
        /// <summary>二段目が始まる撃破数。0 なら二段目そのものが無い。</summary>
        public int Slope2AtKills = 0;
        /// <summary>二段目で、1機ごとに詰める量（ms）。0 なら二段目は効かない。</summary>
        public int Slope2StepMs = 0;
        /// <summary>二段目の行き着く先（ms）。ここより下には行かない。</summary>
        public int Slope2FloorMs = 100;

        /// <summary>倒した数に応じた、今の相手の「考える時間」。</summary>
        public int LagForKills(int kills)
        {
            int lag = StartLagMs - kills * StepLagMs;
            if (lag < FloorLagMs) { lag = FloorLagMs; }

            /* 二段目の坂（9-6o の案A）。**一段目とは別に引く。**
               一段目の計算に混ぜると、まだ下限に届いていない序盤まで速くなる。
               ここは「下限に張り付いたあと」だけに効かせたい。 */
            if (Slope2StepMs > 0 && kills > Slope2AtKills)
            {
                lag -= (kills - Slope2AtKills) * Slope2StepMs;
                if (lag < Slope2FloorMs) { lag = Slope2FloorMs; }
            }
            return lag;
        }

        /// <summary>倒した数に応じた、次の相手の耐久。</summary>
        public double EnemyHpAt(int kills)
        {
            return EnemyHp + EnemyHpGrowth * kills;
        }

        /// <summary>倒した数に応じた、撃破時の回復割合。</summary>
        public double HealAt(int kills)
        {
            double h = HealOnKill * Math.Pow(HealDecay, kills);
            return h < HealFloor ? HealFloor : h;
        }

        public double MultiplierOf(Hand hand)
        {
            return HandMultiplier[(int)hand];
        }

        public int EffectMsOf(Hand hand)
        {
            return EffectMs[(int)hand];
        }

        public int ReloadMsOf(Hand hand)
        {
            return ReloadMs[(int)hand];
        }

        public Balance Clone()
        {
            Balance b = new Balance();
            b.HandMultiplier = (double[])HandMultiplier.Clone();
            b.BaseHp = BaseHp;
            b.MatchLimitMs = MatchLimitMs;
            b.MulScale = MulScale;
            b.FlickMs = FlickMs;
            b.BotLagMs = BotLagMs;
            b.PurgeMs = PurgeMs;
            b.OverwriteLockMs = OverwriteLockMs;
            b.MaxOverwritesPerBuild = MaxOverwritesPerBuild;
            b.EffectMs = (int[])EffectMs.Clone();
            b.ReloadMs = (int[])ReloadMs.Clone();
            b.CarryOverKill = CarryOverKill;
            b.StripOnHit = StripOnHit;
            b.StripChance = StripChance;
            b.SubColorScale = SubColorScale;
            b.SubColorMix = (double[,])SubColorMix.Clone();
            b.ShieldLifeMs = ShieldLifeMs;
            b.GuardCoefficient = GuardCoefficient;
            b.GuardReleaseLagMs = GuardReleaseLagMs;
            b.GuardRequiresComplete = GuardRequiresComplete;
            b.DesperationThreshold = DesperationThreshold;
            b.DesperationMultiplier = DesperationMultiplier;
            b.SupplyLineSize = SupplyLineSize;
            b.PrivateLines = PrivateLines;
            b.DeckCopies = DeckCopies;
            b.InfiniteSupply = InfiniteSupply;
            b.Endless = Endless;
            b.StartLagMs = StartLagMs;
            b.FloorLagMs = FloorLagMs;
            b.StepLagMs = StepLagMs;
            b.EnemyHp = EnemyHp;
            b.HealOnKill = HealOnKill;
            b.EndlessLimitMs = EndlessLimitMs;
            b.EnemyHpGrowth = EnemyHpGrowth;
            b.HealDecay = HealDecay;
            b.HealFloor = HealFloor;
            b.Slope2AtKills = Slope2AtKills;
            b.Slope2StepMs = Slope2StepMs;
            b.Slope2FloorMs = Slope2FloorMs;
            return b;
        }
    }
}
