using System;
using System.Collections.Generic;
using RoboSpeed.Core;

namespace RoboSpeed.Sim
{
    /// <summary>
    /// 調整値を振って、速攻ボットと役狙いボットが拮抗する組み合わせを探す。
    /// 仕様書 9-2「勝率 45〜55%」が合格ライン。
    /// 紙の上では決められない値をここで潰す。
    /// </summary>
    public static class Sweep
    {
        private class Row
        {
            public double Hp;
            public int Overwrite;
            public int Purge;
            public double WinRush;      // 速攻の勝率
            public double DurationSec;
            public double Launches;     // 片側あたりの出撃回数
            public double PureColorPct; // 出撃時にピュアカラーだった割合
            public double PrismPct;

            /// <summary>50%からの隔たり。小さいほど拮抗している。</summary>
            public double Imbalance { get { return Math.Abs(WinRush - 50.0); } }
        }

        public static int Run(string[] args)
        {
            int matches = 400;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            // 振る値。初回の結果（速攻88%・試合15.8秒）を踏まえ、
            // 本拠地を厚くして試合を伸ばし、上書きとパージを安くする方向を探る。
            double[] hps = { 500, 900, 1400, 2000, 2800, 3800 };
            int[] overwrites = { 400, 700, 1000, 1500 };
            int[] purges = { 500, 800, 1200 };

            Console.WriteLine("探索: 本拠地 " + hps.Length + "通り × 上書き " + overwrites.Length
                + "通り × パージ " + purges.Length + "通り = "
                + (hps.Length * overwrites.Length * purges.Length) + "組  各" + matches + "戦");
            Console.WriteLine("目標: 速攻の勝率 45〜55%（仕様書 9-2）");
            Console.WriteLine();

            List<Row> rows = new List<Row>();
            int seed = 9000;

            foreach (double hp in hps)
            foreach (int ow in overwrites)
            foreach (int pg in purges)
            {
                Balance bal = new Balance();
                bal.BaseHp = hp;
                bal.OverwriteLockMs = ow;
                bal.PurgeMs = pg;

                GameSimulator sim = new GameSimulator(bal);
                SimStats st = sim.Run(new RushBot(), new HandBot(), matches, seed++);

                int totalLaunch = 0;
                for (int i = 0; i < 7; i++) { totalLaunch += st.HandAtLaunch[i]; }

                Row r = new Row();
                r.Hp = hp;
                r.Overwrite = ow;
                r.Purge = pg;
                r.WinRush = st.WinRateA;
                r.DurationSec = st.AvgDurationSec;
                r.Launches = st.AvgLaunches;
                r.PureColorPct = totalLaunch == 0 ? 0 : st.HandAtLaunch[(int)Hand.PureColor] * 100.0 / totalLaunch;
                r.PrismPct = totalLaunch == 0 ? 0 : st.HandAtLaunch[(int)Hand.Prism] * 100.0 / totalLaunch;
                rows.Add(r);
            }

            rows.Sort(delegate (Row x, Row y) { return x.Imbalance.CompareTo(y.Imbalance); });

            Console.WriteLine("{0,7} {1,7} {2,7} | {3,7} {4,7} {5,7} {6,7} {7,7}",
                "本拠地", "上書き", "パージ", "速攻勝率", "試合秒", "出撃数", "ピュア%", "プリズム%");
            Console.WriteLine(new string('-', 78));

            int show = Math.Min(15, rows.Count);
            for (int i = 0; i < show; i++)
            {
                Row r = rows[i];
                Console.WriteLine("{0,7:F0} {1,7} {2,7} | {3,6:F1}% {4,7:F1} {5,7:F1} {6,6:F2}% {7,6:F2}%",
                    r.Hp, r.Overwrite, r.Purge, r.WinRush, r.DurationSec, r.Launches, r.PureColorPct, r.PrismPct);
            }

            Console.WriteLine();
            Console.WriteLine("（上位ほど拮抗。試合秒と出撃数が仕様書 9-3 の目安に入るかも併せて見ること）");
            Console.WriteLine("  目安: 1試合の総出撃 8〜14回（片側 4〜7回）");

            // 拮抗していて、かつ出撃回数が目安に入るものを推奨として出す
            Row best = null;
            foreach (Row r in rows)
            {
                if (r.Launches < 4.0 || r.Launches > 7.0) { continue; }
                if (best == null || r.Imbalance < best.Imbalance) { best = r; }
            }

            Console.WriteLine();
            if (best != null)
            {
                Console.WriteLine("推奨（拮抗かつ出撃回数が目安内）:");
                Console.WriteLine(string.Format("  本拠地 {0:F0} / 上書き {1}ms / パージ {2}ms",
                    best.Hp, best.Overwrite, best.Purge));
                Console.WriteLine(string.Format("  速攻勝率 {0:F1}%  試合 {1:F1}秒  出撃 {2:F1}回",
                    best.WinRush, best.DurationSec, best.Launches));
            }
            else
            {
                Console.WriteLine("出撃回数が 4〜7回に入る組み合わせが無い。振る範囲を見直すこと。");
            }
            return 0;
        }

        /// <summary>
        /// 時間コストを振っても拮抗しなかったので、構造そのものを振る。
        ///  ・装填時間の形（仕様どおり／一定／弱い技ほど長い）
        ///  ・役倍率の効き（1.0＝仕様どおり、2.0＝ 1.0 からの差を2倍に伸ばす）
        /// </summary>
        public static int RunStructural(string[] args)
        {
            int matches = 400;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            // 仕様書 6-4 の装填時間。弱い役ほど短く、強い役ほど長い。
            int[] spec = { 200, 300, 600, 900, 1000, 1200, 2000 };
            // 一定。役によって差をつけない。
            int[] flat = { 700, 700, 700, 700, 700, 700, 700 };
            // 反転。弱い技の連打に税をかける。
            int[] inverted = { 1600, 1400, 1100, 800, 700, 600, 400 };

            var profiles = new (string name, int[] reload)[]
            {
                ("仕様どおり", spec),
                ("一定",       flat),
                ("反転",       inverted),
            };
            double[] scales = { 1.0, 1.5, 2.0, 3.0 };
            double[] hps = { 900, 1400 };

            Console.WriteLine("構造探索: 装填の形 3通り × 倍率の効き " + scales.Length
                + "通り × 本拠地 " + hps.Length + "通り  各" + matches + "戦");
            Console.WriteLine("目標: 速攻の勝率 45〜55%");
            Console.WriteLine();
            Console.WriteLine("{0,-10} {1,6} {2,7} | {3,8} {4,7} {5,7} {6,7}",
                "装填", "倍率", "本拠地", "速攻勝率", "試合秒", "出撃数", "ピュア%");
            Console.WriteLine(new string('-', 68));

            int seed = 7000;
            string bestLine = null;
            double bestGap = double.MaxValue;

            foreach (var p in profiles)
            foreach (double sc in scales)
            foreach (double hp in hps)
            {
                Balance bal = new Balance();
                bal.BaseHp = hp;
                bal.OverwriteLockMs = 700;
                bal.PurgeMs = 800;
                bal.ReloadMs = (int[])p.reload.Clone();

                // 1.0 からの差を sc 倍に伸ばす。倍率の効きだけを変える。
                for (int i = 0; i < bal.HandMultiplier.Length; i++)
                {
                    bal.HandMultiplier[i] = 1.0 + (bal.HandMultiplier[i] - 1.0) * sc;
                }

                GameSimulator sim = new GameSimulator(bal);
                SimStats st = sim.Run(new RushBot(), new HandBot(), matches, seed++);

                int total = 0;
                for (int i = 0; i < 7; i++) { total += st.HandAtLaunch[i]; }
                double pure = total == 0 ? 0 : st.HandAtLaunch[(int)Hand.PureColor] * 100.0 / total;

                string line = string.Format("{0,-10} {1,5:F1}x {2,7:F0} | {3,7:F1}% {4,7:F1} {5,7:F1} {6,6:F2}%",
                    p.name, sc, hp, st.WinRateA, st.AvgDurationSec, st.AvgLaunches, pure);
                Console.WriteLine(line);

                double gap = Math.Abs(st.WinRateA - 50.0);
                if (gap < bestGap && st.AvgLaunches >= 3.0 && st.AvgLaunches <= 8.0)
                {
                    bestGap = gap;
                    bestLine = line;
                }
            }

            Console.WriteLine();
            if (bestLine != null)
            {
                Console.WriteLine("最も拮抗（出撃3〜8回の範囲内）:");
                Console.WriteLine("  " + bestLine);
            }
            else
            {
                Console.WriteLine("範囲内に拮抗する組み合わせが無い。");
            }
            return 0;
        }

        /// <summary>
        /// ガードの強さを振る。仕様書 6-2d の「亀化への対策」を数値で詰める。
        /// ガード多用ボットが速攻・役狙いの両方に対して 40〜60% に収まる値を探す。
        /// 削り係数は大きいほどガードが弱い（1.0 で無効果）。
        /// </summary>
        public static int RunGuard(string[] args)
        {
            int matches = 400;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            double[] coefs = { 0.10, 0.20, 0.30, 0.45, 0.60, 0.80 };
            int[] lags = { 300, 700, 1200 };

            Console.WriteLine("ガード探索: 削り係数 " + coefs.Length + "通り × 解除硬直 "
                + lags.Length + "通り  各" + matches + "戦 × 2対戦");
            Console.WriteLine("目標: ガード多用ボットの勝率が両方とも 40〜60%");
            Console.WriteLine();
            Console.WriteLine("{0,7} {1,7} | {2,10} {3,10} {4,8} {5,8}",
                "削り係数", "解除硬直", "対 速攻", "対 役狙い", "ガード数", "被弾数");
            Console.WriteLine(new string('-', 62));

            int seed = 5000;
            double bestScore = double.MaxValue;
            string bestLine = null;

            foreach (double coef in coefs)
            foreach (int lag in lags)
            {
                Balance bal = new Balance();
                bal.GuardCoefficient = coef;
                bal.GuardReleaseLagMs = lag;

                GameSimulator sim = new GameSimulator(bal);
                SimStats vsRush = sim.Run(new GuardBot(), new RushBot(), matches, seed++);
                SimStats vsHand = sim.Run(new GuardBot(), new HandBot(), matches, seed++);

                double wRush = vsRush.WinRateA;
                double wHand = vsHand.WinRateA;
                double guards = (vsRush.Guards + vsHand.Guards) / 4.0 / matches;
                double hits = (vsRush.GuardedHits + vsHand.GuardedHits) / 4.0 / matches;

                string line = string.Format("{0,7:F2} {1,7} | {2,9:F1}% {3,9:F1}% {4,8:F1} {5,8:F1}",
                    coef, lag, wRush, wHand, guards, hits);
                Console.WriteLine(line);

                // 両方の50%からの隔たりの合計。小さいほど良い。
                double score = Math.Abs(wRush - 50.0) + Math.Abs(wHand - 50.0);
                if (score < bestScore) { bestScore = score; bestLine = line; }
            }

            Console.WriteLine();
            Console.WriteLine("最も釣り合う組み合わせ:");
            Console.WriteLine("  " + bestLine);
            Console.WriteLine();
            Console.WriteLine("（削り係数が大きいほどガードは弱い。1.00 で軽減なし）");
            return 0;
        }

        /// <summary>
        /// 山札の枚数を振る。各カードを1〜3枚ずつにして比べる。
        /// 割合は変わらないが、両者の作業台と共有ラインで最大14枚が場に出るため、
        /// 25枚だと狙ったカードが塞がって手に入らない。その枯渇が緩むかを見る。
        /// </summary>
        public static int RunDeck(string[] args)
        {
            int matches = 1000;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            int[] copies = { 1, 2, 3 };

            Console.WriteLine("山札の枚数を振る（各" + matches + "戦）");
            Console.WriteLine("狙い: 狙ったカードが場で塞がる枯渇が緩むか");
            Console.WriteLine();

            int seed = 3000;
            foreach (int c in copies)
            {
                Balance bal = new Balance();
                bal.DeckCopies = c;
                GameSimulator sim = new GameSimulator(bal);

                SimStats st = sim.Run(new RushBot(), new HandBot(), matches, seed++);

                int total = 0;
                for (int i = 0; i < 7; i++) { total += st.HandAtLaunch[i]; }
                double Pct(Hand h) { return total == 0 ? 0 : st.HandAtLaunch[(int)h] * 100.0 / total; }

                Console.WriteLine("--- 各" + c + "枚ずつ = 山札 " + bal.DeckSize + "枚 ---");
                Console.WriteLine(string.Format("  速攻勝率 {0,5:F1}%   試合 {1,5:F1}秒   出撃 {2,4:F1}回   循環 {3,4:F1}回",
                    st.WinRateA, st.AvgDurationSec, st.AvgLaunches, (double)st.RecycleTotal / matches));
                Console.WriteLine(string.Format("  ピュア {0,5:F2}%  フォー {1,5:F2}%  プリズム {2,5:F2}%  フル {3,5:F2}%",
                    Pct(Hand.PureColor), Pct(Hand.FourOfAKind), Pct(Hand.Prism), Pct(Hand.FullHouse)));
                Console.WriteLine(string.Format("  スリー {0,5:F2}%  ツー   {1,5:F2}%  ワン     {2,5:F2}%",
                    Pct(Hand.ThreeOfAKind), Pct(Hand.TwoPair), Pct(Hand.OnePair)));
                Console.WriteLine(string.Format("  上書き {0,4:F1}回   パージ {1,4:F1}回   妨害 {2,4:F1}回",
                    st.AvgOverwrites, st.Discards / 2.0 / matches, st.Stripped / 2.0 / matches));
                Console.WriteLine();
            }

            Console.WriteLine("（割合は同じなので、変化があれば枯渇が原因だったと言える）");
            return 0;
        }

        /// <summary>
        /// 膠着を直接測る。
        ///
        /// 既存の deck は「速攻 vs 8秒で見切る役狙い」で測っていたため、
        /// そもそも粘らないボットどうしで、枯渇が起きる前に決着していた。
        /// ここでは **粘る打ち手どうし** を当てて、山札の枚数が
        /// 「狙った色を取り合って誰も揃わない」状態をどれだけ緩めるかを見る。
        ///
        /// 1色あたりの枚数 = DeckCopies × 5部位。
        /// 25枚（1枚ずつ）だと1色5枚しか無く、相手が1枚握るだけで
        /// ピュアカラーは成立しなくなる。
        /// </summary>
        public static int RunJam(string[] args)
        {
            int matches = 600;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            int[] copies = { 1, 2, 3, 4 };

            Console.WriteLine("膠着の測定（粘る打ち手どうし・各" + matches + "戦 × 3対戦）");
            Console.WriteLine("目標: 時間切れが十分に低く、出撃回数が実用的な水準になる枚数を探す");
            Console.WriteLine();
            Console.WriteLine("{0,6} {1,6} | {2,8} {3,8} {4,8} {5,8} {6,8}",
                "枚ずつ", "山札", "対戦", "時間切れ", "試合秒", "出撃", "パージ");
            Console.WriteLine(new string('-', 72));

            int seed = 9100;
            foreach (int c in copies)
            {
                Balance bal = new Balance();
                bal.DeckCopies = c;
                GameSimulator sim = new GameSimulator(bal);

                var pairs = new (string label, IBot a, IBot b)[]
                {
                    ("フル vs ピュア", new TargetBot(Hand.FullHouse),  new TargetBot(Hand.PureColor)),
                    ("フル vs フル",   new TargetBot(Hand.FullHouse),  new TargetBot(Hand.FullHouse)),
                    ("ピュア vs ピュア", new TargetBot(Hand.PureColor), new TargetBot(Hand.PureColor)),
                };

                bool first = true;
                foreach (var p in pairs)
                {
                    SimStats st = sim.Run(p.a, p.b, matches, seed++);
                    Console.WriteLine(string.Format("{0,6} {1,6} | {2,-14} {3,7:F1}% {4,7:F1}秒 {5,7:F1}回 {6,7:F1}回",
                        first ? c.ToString() : "", first ? bal.DeckSize.ToString() : "",
                        p.label,
                        st.Timeouts * 100.0 / matches,
                        st.AvgDurationSec,
                        st.AvgLaunches,
                        st.Discards / 2.0 / matches));
                    first = false;
                }
                Console.WriteLine();
            }

            Console.WriteLine("1色あたりの枚数 = 枚ずつ × 5部位。");
            Console.WriteLine("25枚だと1色5枚しか無く、相手が1枚握るだけでピュアカラーが成立しない。");
            return 0;
        }

        /// <summary>
        /// 役倍率の傾きを振って、「速く撃つ」と「良い役を狙う」が釣り合う点を探す。
        ///
        /// v1.7 で仕様が大きく変わった（私有ライン・部位破壊・パージ廃止・技の自動決定）ため、
        /// 9-2d／9-5i で決めた倍率はすべて測り直しになる。
        /// </summary>
        public static int RunMulScale(string[] args)
        {
            int matches = 600;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            double[] scales = { 1.5, 2.0, 2.5, 3.0 };
            double[] chances = { 0.25, 0.40, 0.55, 0.70 };

            Console.WriteLine("役倍率の傾きを振る（各" + matches + "戦 × 3対戦）");
            Console.WriteLine("目標: 役を狙う打ち手が 対速攻で 45〜55%");
            Console.WriteLine("※ ボットの1手の間 " + new Balance().BotLagMs + "ms（人間の速さに寄せた値）");
            Console.WriteLine();
            Console.WriteLine("{0,6} {1,6} {2,9} | {3,10} {4,10} {5,10} | {6,9}",
                "破壊率", "傾き", "ピュア倍率", "フル狙い", "ピュア狙い", "プリズム狙い", "試合秒");
            Console.WriteLine(new string('-', 84));

            int seed = 11000;
            foreach (double ch in chances)
            foreach (double sc in scales)
            {
                Balance bal = new Balance();
                bal.MulScale = sc;
                bal.StripChance = ch;
                GameSimulator sim = new GameSimulator(bal);

                SimStats f = sim.Run(new TargetBot(Hand.FullHouse), new RushBot(), matches, seed++);
                SimStats p = sim.Run(new TargetBot(Hand.PureColor), new RushBot(), matches, seed++);
                SimStats r = sim.Run(new TargetBot(Hand.Prism),     new RushBot(), matches, seed++);

                Console.WriteLine("{0,6} {1,5:F1}x {2,8:F2}x | {3,9:F1}% {4,9:F1}% {5,9:F1}% | {6,8:F1}秒",
                    (ch * 100).ToString("F0") + "%", sc, bal.MultiplierOfScaled(Hand.PureColor),
                    f.WinRateA, p.WinRateA, r.WinRateA, f.AvgDurationSec);
            }

            Console.WriteLine();
            Console.WriteLine("勝率は **役狙い側**。50%に近いほど釣り合っている。");
            return 0;
        }

        /// <summary>
        /// 共有ラインの表示枚数を振る。
        ///
        /// 山札を増やす以外の膠着対策の候補。
        /// 見えている札が増えれば狙った色に当たりやすくなり、
        /// パージの空振りが減るはず。こちらもアートの作業量は増えない。
        ///
        /// ただし枚数を増やすほど画面が狭くなり、
        /// 4枚でも0.8秒で把握しきれなかった（10-1b の判別テスト）ことに注意。
        /// **数値が良くても、実機で見きれない枚数は採用できない。**
        /// </summary>
        public static int RunLineSize(string[] args)
        {
            int matches = 600;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            int[] sizes = { 4, 5, 6, 8 };
            int[] decks = { 1, 2 };

            Console.WriteLine("共有ラインの表示枚数を振る（各" + matches + "戦）");
            Console.WriteLine();
            Console.WriteLine("{0,5} {1,5} | {2,9} {3,9} {4,9} | {5,10} {6,10}",
                "山札", "ライン", "膠着率", "膠着時出撃", "パージ", "速攻vsフル", "速攻vsピュア");
            Console.WriteLine(new string('-', 78));

            int seed = 9700;
            foreach (int d in decks)
            {
                foreach (int s in sizes)
                {
                    Balance bal = new Balance();
                    bal.DeckCopies = d;
                    bal.SupplyLineSize = s;
                    GameSimulator sim = new GameSimulator(bal);

                    SimStats jam = sim.Run(new TargetBot(Hand.FullHouse),
                                           new TargetBot(Hand.PureColor), matches, seed++);
                    double wFull = sim.Run(new RushBot(), new TargetBot(Hand.FullHouse), matches, seed++).WinRateA;
                    double wPure = sim.Run(new RushBot(), new TargetBot(Hand.PureColor), matches, seed++).WinRateA;

                    Console.WriteLine(string.Format(
                        "{0,5} {1,5} | {2,8:F1}% {3,8:F1}回 {4,8:F1}回 | {5,9:F1}% {6,9:F1}%",
                        bal.DeckSize, s,
                        jam.Timeouts * 100.0 / matches, jam.AvgLaunches,
                        jam.Discards / 2.0 / matches, wFull, wPure));
                }
                Console.WriteLine();
            }

            Console.WriteLine("勝率はすべて **速攻側**。膠着率＝粘る打ち手どうしの時間切れ率。");
            return 0;
        }

        /// <summary>
        /// 上書きの回数制限を振る。
        ///
        /// 問いは2つ。
        ///  (1) 回数制限は、山札50枚の**代わり**に膠着を解けるか（25枚のまま解決するか）
        ///  (2) 50枚と併用したとき、残った2件（プリズム・ガード）に効くか
        ///
        /// 上限に達すると、それ以上機体を直せないので**撃つしかなくなる**。
        /// 時間ではなく回数で頭打ちにする対策なので、粘る打ち手に直接効くはず。
        /// </summary>
        public static int RunOverwriteCap(string[] args)
        {
            int matches = 600;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            int[] caps = { 0, 1, 2, 3, 5 };
            int[] decks = { 1, 2 };

            Console.WriteLine("上書きの回数制限を振る（各" + matches + "戦）");
            Console.WriteLine("0 = 無制限。上限に達すると、直せないので出撃するしかなくなる。");
            Console.WriteLine();
            Console.WriteLine("{0,5} {1,5} | {2,9} {3,9} | {4,9} {5,9} {6,9} {7,9}",
                "山札", "上限", "膠着率", "膠着時出撃", "速攻vsフル", "速攻vsピュア",
                "速攻vsプリズム", "速攻vsガード");
            Console.WriteLine(new string('-', 96));

            int seed = 9500;
            foreach (int d in decks)
            {
                foreach (int cap in caps)
                {
                    Balance bal = new Balance();
                    bal.DeckCopies = d;
                    bal.MaxOverwritesPerBuild = cap;
                    GameSimulator sim = new GameSimulator(bal);

                    // 膠着の代表例：粘る打ち手どうし
                    SimStats jam = sim.Run(new TargetBot(Hand.FullHouse),
                                           new TargetBot(Hand.PureColor), matches, seed++);

                    double wFull  = sim.Run(new RushBot(), new TargetBot(Hand.FullHouse), matches, seed++).WinRateA;
                    double wPure  = sim.Run(new RushBot(), new TargetBot(Hand.PureColor), matches, seed++).WinRateA;
                    double wPrism = sim.Run(new RushBot(), new TargetBot(Hand.Prism),     matches, seed++).WinRateA;
                    double wGuard = sim.Run(new RushBot(), new GuardBot(),                matches, seed++).WinRateA;

                    Console.WriteLine(string.Format(
                        "{0,5} {1,5} | {2,8:F1}% {3,8:F1}回 | {4,8:F1}% {5,8:F1}% {6,8:F1}% {7,8:F1}%",
                        bal.DeckSize, cap == 0 ? "無" : cap.ToString(),
                        jam.Timeouts * 100.0 / matches, jam.AvgLaunches,
                        wFull, wPure, wPrism, wGuard));
                }
                Console.WriteLine();
            }

            Console.WriteLine("勝率はすべて **速攻側**。50%に近いほど釣り合っている。");
            Console.WriteLine("膠着率＝粘る打ち手どうしの時間切れ率。0%が目標。");
            return 0;
        }

        /// <summary>
        /// プリズムの倍率を振る。
        /// 「5色を1枚ずつ」は狙えば4〜5割で達成できるため、理論上の希少度（3.84%）で
        /// 倍率を決めると強すぎた。達成難易度に合わせて下げ、
        /// プリズムの価値は「必殺技を5つ全部使える」側（6-2c）で持たせる。
        /// </summary>
        public static int RunPrism(string[] args)
        {
            int matches = 1200;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            double[] muls = { 3.15, 3.20, 3.25, 3.30, 3.35, 3.40 };

            Console.WriteLine("プリズム倍率の探索（各" + matches + "戦 × 2対戦）");
            Console.WriteLine("目標: プリズム狙いボットが速攻・役狙いの両方に対して 45〜55%");
            Console.WriteLine();
            Console.WriteLine("{0,8} | {1,10} {2,10} {3,10}",
                "倍率", "対 速攻", "対 役狙い", "プリズム率");
            Console.WriteLine(new string('-', 46));

            int seed = 6100;
            double bestScore = double.MaxValue;
            double bestMul = 0;

            foreach (double mul in muls)
            {
                Balance bal = new Balance();
                bal.HandMultiplier[(int)Hand.Prism] = mul;
                GameSimulator sim = new GameSimulator(bal);

                SimStats vsRush = sim.Run(new PrismBot(), new RushBot(), matches, seed++);
                SimStats vsHand = sim.Run(new PrismBot(), new HandBot(), matches, seed++);

                int total = 0;
                for (int i = 0; i < 7; i++) { total += vsRush.HandAtLaunch[i]; }
                double prism = total == 0 ? 0 : vsRush.HandAtLaunch[(int)Hand.Prism] * 100.0 / total;

                Console.WriteLine(string.Format("{0,8:F2} | {1,9:F1}% {2,9:F1}% {3,9:F2}%",
                    mul, vsRush.WinRateA, vsHand.WinRateA, prism));

                double score = Math.Abs(vsRush.WinRateA - 50.0) + Math.Abs(vsHand.WinRateA - 50.0);
                if (score < bestScore) { bestScore = score; bestMul = mul; }
            }

            Console.WriteLine();
            Console.WriteLine(string.Format("最も釣り合う倍率: ×{0:F2}", bestMul));
            Console.WriteLine("（プリズムの差別化は倍率ではなく、必殺技を5つ全部使える点で行う）");
            return 0;
        }

        /// <summary>
        /// 供給方式（捨て札の循環 / 無限に湧く）と、
        /// プリズム狙いが戦術として成立するかを、まとめて確かめる。
        /// </summary>
        public static int RunStrategies(string[] args)
        {
            int matches = 1500;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            var supplies = new (string name, bool infinite)[]
            {
                ("捨て札の循環", false),
                ("無限に湧く",   true),
            };

            int seed = 4100;
            foreach (var sup in supplies)
            {
                Balance bal = new Balance();
                bal.InfiniteSupply = sup.infinite;
                GameSimulator sim = new GameSimulator(bal);

                Console.WriteLine("################ 供給方式: " + sup.name + " ################");
                Console.WriteLine();

                var pairs = new (IBot a, IBot b)[]
                {
                    (new RushBot(),  new HandBot()),
                    (new RushBot(),  new PrismBot()),
                    (new HandBot(),  new PrismBot()),
                    (new PrismBot(), new GuardBot()),
                };

                foreach (var p in pairs)
                {
                    SimStats st = sim.Run(p.a, p.b, matches, seed++);
                    int total = 0;
                    for (int i = 0; i < 7; i++) { total += st.HandAtLaunch[i]; }
                    double pure = total == 0 ? 0 : st.HandAtLaunch[(int)Hand.PureColor] * 100.0 / total;
                    double prism = total == 0 ? 0 : st.HandAtLaunch[(int)Hand.Prism] * 100.0 / total;

                    Console.WriteLine(string.Format("{0,-14} vs {1,-14} : {2,5:F1}% : {3,5:F1}%   試合{4,5:F1}秒  出撃{5,4:F1}回  ピュア{6,5:F2}%  プリズム{7,5:F2}%",
                        p.a.Name, p.b.Name, st.WinRateA, 100.0 - st.WinRateA,
                        st.AvgDurationSec, st.AvgLaunches, pure, prism));
                }
                Console.WriteLine();
            }
            return 0;
        }

        /// <summary>
        /// 副色の効果の強さを振る。仕様書 9-5n。
        ///
        /// 副色は「主色以外で最も多い色」で、立つのは
        /// ツーペア・フルハウス・フォーカードの3役だけ（実機ログで出撃の44%）。
        /// 効果は追加ダメージ／回復／シールドへの **配分** で、総量は色によらず一定。
        ///
        /// 見たいのは2つ。
        ///   (1) 役を狙う側がどれだけ強くなるか（0.0のとき 対速攻 53.8%）
        ///   (2) **回復で試合が終わらなくなっていないか**（試合時間が伸び続けないか）
        ///
        /// 注意：ボットは副色を **狙っていない**。組んだ結果として付くだけなので、
        /// ここで出るのは「受け身の効果」。人間が狙って取りに行けば、これより強く出る。
        /// </summary>
        /// <summary>
        /// テトリス型の走りを測る。仕様書 9-6d。
        ///
        /// ---- 計測器の較正 ----
        ///
        /// 既定の BotLagMs 900 だと、ボットの組み立ては (400+900)×5 = **6.5秒**。
        /// 実機のあなたは **10.2秒**（3回の平均）。この差を入れずに測ると、
        /// 「もっと先まで行ける打ち手」の数字が出てしまい、平地の長さを見誤る。
        ///
        ///   (400 + lag) × 5 = 10200  →  lag = 1640ms
        ///
        /// 9-2d／9-5i／9-7 と同じ轍を踏まないよう、**測る前に合わせる。**
        /// </summary>
        /// <summary>
        /// 打ち手の組み立て時間が実機に合う「考える時間」を、実測で探す。
        ///
        /// 計算で出そうとすると、引き直しや上書きの回数を勘定に入れ忘れる。
        /// **走らせて出た秒数で合わせるほうが確実。**
        /// </summary>
        private static int CalibrateLag(IBot bot, double targetSec, int runs)
        {
            int lo = 100, hi = 2500, best = 900;
            double bestGap = double.MaxValue, bestSec = 0;

            Console.WriteLine("較正: 組み立てが " + targetSec.ToString("F1") + "秒 になる遅さを探す");
            for (int step = 0; step < 12 && lo <= hi; step++)
            {
                int mid = (lo + hi) / 2;
                Balance bal = new Balance();
                GameSimulator sim = new GameSimulator(bal);
                EndlessStats es = sim.RunEndless(bot, new RushBot(), mid, runs, 41000 + step);

                double sec = es.AvgBuildSec;
                double gap = Math.Abs(sec - targetSec);
                if (gap < bestGap) { bestGap = gap; best = mid; bestSec = sec; }

                if (sec < targetSec) { lo = mid + 1; } else { hi = mid - 1; }
            }

            Console.WriteLine("  → 1手 " + best + "ms のとき 組み立て " + bestSec.ToString("F1") + "秒");
            Console.WriteLine();
            return best;
        }

        /// <summary>
        /// **狙う役ごとに、テトリス型の走りで撃破数を比べる。**（仕様書 9-6h）
        ///
        ///   dotnet run -- aim [本数]
        ///
        /// 試遊で「フルハウスだけ狙えばいい、になりそうで面白くない」と出た。
        /// 戦略が一本に潰れているかは、**狙いを変えて走らせれば分かる。**
        ///
        /// 見たいのは撃破数の差。**どれか1つが突出していれば、それが唯一の正解**になる。
        /// 差が小さいなら、狙いの選択は好みの範囲として成立している。
        /// 「粘り」は、その役に届くまで何ミリ秒待つか。長いほど強欲。
        /// </summary>
        public static int RunAim(string[] args)
        {
            int runs = 200;
            if (args.Length > 1) { int.TryParse(args[1], out runs); }

            const int humanLag = 900;

            var aims = new (string name, Func<IBot> make)[]
            {
                ("速攻",   () => new RushBot()),
                ("2ペア",  () => new HandBot(Hand.TwoPair, 2000)),
                ("3カード",() => new HandBot(Hand.ThreeOfAKind, 2000)),
                ("フル",   () => new HandBot(Hand.FullHouse, 2000)),
                ("4カード",() => new HandBot(Hand.FourOfAKind, 3000)),
                ("ピュア", () => new HandBot(Hand.PureColor, 4000)),
                ("プリズム",() => new PrismBot()),
            };

            /* 役の差を出す手を並べる。**攻撃力は下げない。**
                 ・倍率の傾き（MulScale）を上げる … 上位役だけが強くなる
                 ・敵の耐久を上げる               … 差が出る「刻み」が増える
                 ・装填時間の幅を広げる           … 上位役ほど次が速く撃てる
               装填は **整数に丸まらない** ので、敵の耐久が低くても差が残る。 */
            var plans = new (string name, Action<Balance> set)[]
            {
                ("採用値(持越/HP600/傾7)", b => { }),
                ("傾き4.0",              b => { b.MulScale = 4.0; }),
                ("傾き5.0",              b => { b.MulScale = 5.0; }),
                ("傾き6.0",              b => { b.MulScale = 6.0; }),
                ("敵HP600",              b => { b.EnemyHp = 600.0; }),
                ("敵HP600+傾き4.0",       b => { b.EnemyHp = 600.0; b.MulScale = 4.0; }),
                ("装填を広げる",           b => { b.ReloadMs = new[] { 2200, 1800, 1300, 800, 600, 450, 250 }; }),
                ("装填広げ+傾き4.0",       b => { b.ReloadMs = new[] { 2200, 1800, 1300, 800, 600, 450, 250 };
                                                 b.MulScale = 4.0; }),
                ("装填広げ+敵HP600",       b => { b.ReloadMs = new[] { 2200, 1800, 1300, 800, 600, 450, 250 };
                                                 b.EnemyHp = 600.0; }),

                /* ---- 余ったダメージを次の機体へ持ち越す ----
                   **捨てているから、強い役に見返りが出ない。**
                   敵420に対しピュアの633は213を捨てている。持ち越せば無駄が消え、
                   ダメージがそのまま撃破数に変わる。 */
                /* 持ち越しを前提に、**幅（傾き）と耐久**を格子で振る。
                   幅を広げるほど上位役が強くなり、耐久を上げるほど
                   「何発で倒すか」の刻みが増える。**両方が要るはず**という読み。 */
                ("持越 HP420 傾5",   b => { b.CarryOverKill = true; b.MulScale = 5.0; }),
                ("持越 HP420 傾7",   b => { b.CarryOverKill = true; b.MulScale = 7.0; }),
                ("持越 HP600 傾5",   b => { b.CarryOverKill = true; b.EnemyHp = 600.0; b.MulScale = 5.0; }),
                ("持越 HP600 傾7",   b => { b.CarryOverKill = true; b.EnemyHp = 600.0; b.MulScale = 7.0; }),
                ("持越 HP800 傾5",   b => { b.CarryOverKill = true; b.EnemyHp = 800.0; b.MulScale = 5.0; }),
                ("持越 HP800 傾7",   b => { b.CarryOverKill = true; b.EnemyHp = 800.0; b.MulScale = 7.0; }),
                ("持越 HP800 傾9",   b => { b.CarryOverKill = true; b.EnemyHp = 800.0; b.MulScale = 9.0; }),
                ("持越 HP1100 傾7",  b => { b.CarryOverKill = true; b.EnemyHp = 1100.0; b.MulScale = 7.0; }),
                ("持越 HP1100 傾9",  b => { b.CarryOverKill = true; b.EnemyHp = 1100.0; b.MulScale = 9.0; }),
            };

            Console.WriteLine("狙う役ごとの撃破数（各" + runs + "本、1手" + humanLag + "ms）");
            Console.WriteLine("**上位役ほど数字が大きくなるのが理想。** 横並びなら狙いに意味が無い。");
            Console.WriteLine();
            Console.Write("{0,-20}", "設計");
            foreach (var a in aims) { Console.Write("{0,8}", a.name); }
            Console.WriteLine("{0,8}{1,9}", "差", "最良の狙い");
            Console.WriteLine(new string('-', 20 + 8 * aims.Length + 17));

            int seed = 51000;
            foreach (var p in plans)
            {
                Balance bal = new Balance();
                p.set(bal);
                GameSimulator sim = new GameSimulator(bal);

                Console.Write("{0,-20}", p.name);
                double best = 0.0, worst = 1e9;
                string bestName = "";
                foreach (var a in aims)
                {
                    EndlessStats es = sim.RunEndless(a.make(), new RushBot(), humanLag, runs, seed++);
                    if (es.AvgKills > best) { best = es.AvgKills; bestName = a.name; }
                    if (es.AvgKills < worst) { worst = es.AvgKills; }
                    Console.Write("{0,8:F1}", es.AvgKills);
                }
                Console.WriteLine("{0,8:F1}{1,9}", best - worst, bestName);
            }

            Console.WriteLine();
            Console.WriteLine("**差** が大きいほど、狙いの選択が結果に効いている。");
            Console.WriteLine("**最良の狙い** が上位役になっているほど、欲張る価値がある。");
            return 0;
        }

        public static int RunEndless(string[] args)
        {
            int runs = 300;
            if (args.Length > 1) { int.TryParse(args[1], out runs); }

            // ---- 打ち手の模型（9-6e で作り直した）----
            //
            // 当初は TargetBot(スリーカード) を組み立て時間10.2秒に合わせて使っていたが、
            // **2か所とも間違っていた。**
            //
            //   (1) TargetBot は届くまで撃たないので **ワンペアを1回も撃たない**。
            //       実機は出撃の36%がワンペア。まったく別の打ち手だった。
            //   (2) 「時間」で較正すると 1手428〜553ms になり、同じ10.2秒で
            //       10.7手 打ててしまう。実機は7.6手。**実質的に賢い打ち手**になっていた。
            //
            // 正しい軸は **1手のコスト**。実機288手／370.7秒 = 1手1.29秒、
            // フリック400msを引いて **900ms**（既定値がほぼ正解だった）。
            // 粘りは実測の最良値 2000ms（「改善する上書きが1つあれば拾い、あとは撃つ」）。
            const int humanLag = 900;
            IBot human = new HandBot(Hand.FullHouse, 2000);

            var plans = new (string name, Action<Balance> set)[]
            {
                ("採用値(持越/HP600/傾7)", b => { }),
                /* 比べる相手は **その時点の既定を全部戻したもの** にすること。
                   一部だけ戻すと、新しい既定が混ざって「旧」の行が旧でなくなる。 */
                ("旧v1.9(段220/HP1400/敵700/回35)",
                    b => { b.StepLagMs = 220; b.BaseHp = 1400.0; b.EnemyHp = 700.0; b.HealOnKill = 0.35; }),
                ("一つ前(段140/敵700/回35)",
                    b => { b.StepLagMs = 140; b.EnemyHp = 700.0; b.HealOnKill = 0.35; }),
                ("段だけ戻す(140)",    b => { b.StepLagMs = 140; }),
                ("敵HPだけ戻す(700)",  b => { b.EnemyHp = 700.0; }),
                ("回復だけ戻す(35)",   b => { b.HealOnKill = 0.35; }),
                ("旧・下限500",        b => { b.FloorLagMs = 500; }),
                ("段をさらに細かく110",  b => { b.StepLagMs = 110; }),
                ("下限200",            b => { b.FloorLagMs = 200; }),
                ("敵HP +60/機",       b => { b.EnemyHpGrowth = 60; }),
                ("回復 -10%/機",      b => { b.HealDecay = 0.90; }),

                /* ---- 「24機くらい行けるように」を探す（試遊の要望）----
                   いまは平均 8.9機。**倍以上に伸ばす必要がある。**
                   効く軸は3つ。どれを回すかで走りの性格が変わる。
                     ・敵HP を下げる  … 1機が早く落ちる。節目の間隔が縮む
                     ・回復を上げる    … 粘れる。1機の重みは変わらない
                     ・段を緩める      … 敵が速くならない。終盤の圧が落ちる  */
                ("A 敵HP 450",         b => { b.EnemyHp = 450.0; }),
                ("B 敵HP 350",         b => { b.EnemyHp = 350.0; }),
                ("C 回復 50%",         b => { b.HealOnKill = 0.50; }),
                ("D 回復 60%",         b => { b.HealOnKill = 0.60; }),
                ("E 段90",             b => { b.StepLagMs = 90; }),
                ("F 敵HP450+回復50",   b => { b.EnemyHp = 450.0; b.HealOnKill = 0.50; }),
                ("G 敵HP450+段90",     b => { b.EnemyHp = 450.0; b.StepLagMs = 90; }),
                ("H 敵HP350+回復50",   b => { b.EnemyHp = 350.0; b.HealOnKill = 0.50; }),
                ("I 敵HP450+回復45+段100",
                    b => { b.EnemyHp = 450.0; b.HealOnKill = 0.45; b.StepLagMs = 100; }),
                ("J 敵HP400+回復50+段90",
                    b => { b.EnemyHp = 400.0; b.HealOnKill = 0.50; b.StepLagMs = 90; }),
                ("K 敵HP400+回復45+段80",
                    b => { b.EnemyHp = 400.0; b.HealOnKill = 0.45; b.StepLagMs = 80; }),
                ("L 敵HP350+回復45+段90",
                    b => { b.EnemyHp = 350.0; b.HealOnKill = 0.45; b.StepLagMs = 90; }),
                ("M 敵HP450+回復45+段80",
                    b => { b.EnemyHp = 450.0; b.HealOnKill = 0.45; b.StepLagMs = 80; }),
                /* K は 20機到達60% まで来たが「終わらない走り」が出た。
                   **青天井はランキングを壊す**ので、その手前を探す。
                   敵の耐久を戻して落ちにくくし、段（加速）で圧を保つ。 */
                ("N 敵HP420+回復45+段80",
                    b => { b.EnemyHp = 420.0; b.HealOnKill = 0.45; b.StepLagMs = 80; }),
                ("O 敵HP450+回復45+段70",
                    b => { b.EnemyHp = 450.0; b.HealOnKill = 0.45; b.StepLagMs = 70; }),
                ("P 敵HP420+回復42+段75",
                    b => { b.EnemyHp = 420.0; b.HealOnKill = 0.42; b.StepLagMs = 75; }),

                /* ---- 終盤の締めを足す ----
                   **敵の速さには下限（3.5秒）がある。** そこを超えて速い打ち手は
                   永遠に死なない。平均を24に寄せるほど「終わらない走り」が増える（O で12%）。
                   速さ以外で後半だけ効く圧を足せば、**序盤は易しいまま、終わりは来る。**
                     ・敵HPが1機ごとに増える  … 倒すのに時間がかかるようになる
                     ・回復が1機ごとに減る    … 粘りが効かなくなる */
                ("Q 楽な土台+敵HP+25/機",
                    b => { b.EnemyHp = 420.0; b.HealOnKill = 0.45; b.StepLagMs = 80; b.EnemyHpGrowth = 25; }),
                ("R 楽な土台+回復-3%/機",
                    b => { b.EnemyHp = 420.0; b.HealOnKill = 0.45; b.StepLagMs = 80; b.HealDecay = 0.97; }),
                ("S さらに楽+敵HP+30/機",
                    b => { b.EnemyHp = 400.0; b.HealOnKill = 0.50; b.StepLagMs = 70; b.EnemyHpGrowth = 30; }),
                ("T さらに楽+回復-4%/機",
                    b => { b.EnemyHp = 400.0; b.HealOnKill = 0.50; b.StepLagMs = 70; b.HealDecay = 0.96; }),

                /* ---- 敵の耐久を段階的に上げる案（試遊者の提案）----
                   「500 から始めて1機ごとに +10。20機目で 700」。
                   **序盤は easy、終盤は歯ごたえ**という狙い。
                   +60/機 は効きすぎて逆効果だったが（S）、+10 なら緩やかに効く。 */
                ("U 敵HP500+10/機",
                    b => { b.EnemyHp = 500.0; b.EnemyHpGrowth = 10; }),
                ("V 敵HP500+15/機",
                    b => { b.EnemyHp = 500.0; b.EnemyHpGrowth = 15; }),
                ("W 敵HP480+10/機",
                    b => { b.EnemyHp = 480.0; b.EnemyHpGrowth = 10; }),
                ("X 敵HP500+10/機+段70",
                    b => { b.EnemyHp = 500.0; b.EnemyHpGrowth = 10; b.StepLagMs = 70; }),
                ("Y 敵HP450+10/機",
                    b => { b.EnemyHp = 450.0; b.EnemyHpGrowth = 10; }),

                /* ---- 終盤の圧は「耐久」ではなく「速さ」で作る ----
                   **敵の耐久は難しさではなくテンポを決める。**
                   走りが終わるのは *自分* が落ちたときで、敵が硬くなっても
                   こちらの危険は増えない。増えるのは待ち時間だけ。
                   終盤を難しくしたいなら、**速さの下限を下げる**のが直接効く。 */
                /* 9-6h の候補。**持ち越し＋耐久600＋傾き7** で上位役が勝つようになる。
                   ここでは「走りが終わるか」「何分かかるか」を見る。 */
                ("候補 持越/HP600/傾7",
                    b => { b.CarryOverKill = true; b.EnemyHp = 600.0; b.MulScale = 7.0; }),
                ("候補 持越/HP600/傾7/下限200",
                    b => { b.CarryOverKill = true; b.EnemyHp = 600.0; b.MulScale = 7.0; b.FloorLagMs = 200; }),
                ("候補 持越/HP500/傾7",
                    b => { b.CarryOverKill = true; b.EnemyHp = 500.0; b.MulScale = 7.0; }),

                ("Z 下限200(3.0秒)",   b => { b.FloorLagMs = 200; }),
                ("AA 下限120(2.6秒)",  b => { b.FloorLagMs = 120; }),
                ("AB 下限60(2.3秒)",   b => { b.FloorLagMs = 60; }),
            };

            Console.WriteLine("テトリス型の走りを測る（各" + runs + "本、1手900ms・粘り2000msの打ち手）");
            Console.WriteLine("見たいのは **下限に達したあと何秒走るか**。長いほど加速が仕事をしていない。");
            Console.WriteLine();
            // 試遊で「20機は簡単に行けるように」と出たので、**20機と24機の到達率**も見る。
            Console.WriteLine("{0,-20} {1,7} {2,8} {3,6} {4,7} {5,8} {6,8} {7,8}",
                "進行の設計", "撃破", "生存秒", "最高", "平地%", "10機到達", "20機到達", "24機到達");
            Console.WriteLine(new string('-', 82));

            int seed = 31000;
            foreach (var p in plans)
            {
                Balance bal = new Balance();
                p.set(bal);
                GameSimulator sim = new GameSimulator(bal);
                EndlessStats es = sim.RunEndless(human, new RushBot(), humanLag, runs, seed++);

                // HandsAtKill[k] は「k機目に到達した走りの数」＝生存曲線。
                // 平地がどれだけ効いているかは、**下限より先まで行った割合**で見る。
                double reach10 = es.HandsAtKill[10] * 100.0 / runs;
                double reach20 = es.HandsAtKill[20] * 100.0 / runs;
                double reach24 = es.HandsAtKill[24] * 100.0 / runs;

                Console.WriteLine("{0,-20} {1,6:F1}機 {2,7:F1}秒 {3,5}機 {4,6:F0}% {5,7:F0}% {6,7:F0}% {7,7:F0}%",
                    p.name, es.AvgKills, es.AvgSec, es.BestKills,
                    es.FlatPct, reach10, reach20, reach24);
                if (es.NeverDied > 0)
                {
                    Console.WriteLine("    ※ " + es.NeverDied + "本が制限時間まで落ちなかった＝終わらない設計");
                }
            }

            Console.WriteLine();
            Console.WriteLine("実機の実測（下限500の頃）: 7機/376秒、8機/371秒。下限500では平地18%だった。");
            return 0;
        }

        /// <summary>
        /// **難易度の3段階を、敵の速さだけで作れるかを測る。**（仕様書 9-6k）
        ///
        ///   dotnet run -- diff [本数]
        ///
        /// 実機の指示は「**敵の加速の刻みと、行き着く敵の秒数**を変えれば行ける」。
        /// つまり動かすのは StepLagMs と FloorLagMs の2つだけ。
        /// 敵の耐久・回復量・本拠地のHP・手触り（フリック、上書き、倍率）には
        /// **一切触らない。** 触ると「イージーだと操作が変」になる。
        ///
        /// 見たいのは撃破数の段差。**3つ選んだときに、はっきり差が出るか。**
        /// あわせて「終わらない走り」が出ていないかも見る（青天井は順位表を壊す）。
        /// </summary>
        public static int RunDiff(string[] args)
        {
            int runs = 200;
            if (args.Length > 1) { int.TryParse(args[1], out runs); }

            // RunEndless と同じ打ち手（1手900ms・粘り2000ms）。比較できる軸を変えない。
            const int humanLag = 900;

            int[] floors = { 200, 240, 300, 360, 400, 450 };
            int[] steps  = { 60, 70, 80, 90, 100, 120 };

            Balance baseline = new Balance();
            Console.WriteLine("難易度を敵の速さだけで作る（各" + runs + "本、1手900ms・粘り2000msの打ち手）");
            Console.WriteLine("既定は 下限" + baseline.FloorLagMs + "ms / 刻み" + baseline.StepLagMs + "ms（＝ノーマル）");
            Console.WriteLine("敵の耐久・回復・本拠地HP・手触りは **どの段でも同じ**。");
            Console.WriteLine();

            // ---- 撃破数の表 ----
            Console.WriteLine("【平均撃破数】 行＝下限(ms)／列＝刻み(ms)");
            Console.Write("{0,8}", "");
            foreach (int s in steps) { Console.Write("{0,8}", s); }
            Console.WriteLine();
            Console.WriteLine(new string('-', 8 + steps.Length * 8));

            var kills = new double[floors.Length, steps.Length];
            var reach = new double[floors.Length, steps.Length];
            var never = new int[floors.Length, steps.Length];
            var secs  = new double[floors.Length, steps.Length];

            int seed = 71000;
            for (int i = 0; i < floors.Length; i++)
            {
                Console.Write("{0,7}:", floors[i]);
                for (int j = 0; j < steps.Length; j++)
                {
                    Balance bal = new Balance();
                    bal.FloorLagMs = floors[i];
                    bal.StepLagMs  = steps[j];
                    GameSimulator sim = new GameSimulator(bal);
                    EndlessStats es = sim.RunEndless(new HandBot(Hand.FullHouse, 2000),
                                                     new RushBot(), humanLag, runs, seed++);
                    kills[i, j] = es.AvgKills;
                    reach[i, j] = es.HandsAtKill[20] * 100.0 / runs;
                    never[i, j] = es.NeverDied;
                    secs[i, j]  = es.AvgSec;
                    Console.Write("{0,8:F1}", es.AvgKills);
                }
                Console.WriteLine();
            }
            Console.WriteLine();

            // ---- 走りの長さ。**長すぎる段は採れない。** ----
            Console.WriteLine("【平均の生存秒】 長すぎる段は1回が重くなりすぎる");
            Console.Write("{0,8}", "");
            foreach (int s in steps) { Console.Write("{0,8}", s); }
            Console.WriteLine();
            Console.WriteLine(new string('-', 8 + steps.Length * 8));
            for (int i = 0; i < floors.Length; i++)
            {
                Console.Write("{0,7}:", floors[i]);
                for (int j = 0; j < steps.Length; j++) { Console.Write("{0,8:F0}", secs[i, j]); }
                Console.WriteLine();
            }
            Console.WriteLine();

            // ---- 終わらない走り。**1本でも出たらその段は採らない。** ----
            Console.WriteLine("【終わらなかった走り】 0 でない段は青天井＝順位表が壊れる");
            Console.Write("{0,8}", "");
            foreach (int s in steps) { Console.Write("{0,8}", s); }
            Console.WriteLine();
            Console.WriteLine(new string('-', 8 + steps.Length * 8));
            for (int i = 0; i < floors.Length; i++)
            {
                Console.Write("{0,7}:", floors[i]);
                for (int j = 0; j < steps.Length; j++) { Console.Write("{0,8}", never[i, j]); }
                Console.WriteLine();
            }
            Console.WriteLine();

            // ---- 頭打ちに達する機と、そのときの組み立て秒 ----
            Console.WriteLine("【参考】下限に達する機と、そのときの敵の組み立て秒（フリック400ms込み）");
            foreach (int f in floors)
            {
                Console.Write("  下限{0,4}ms → 組み立て {1:F1}秒 ／ 頭打ちは ", f, (400 + f) * 5 / 1000.0);
                foreach (int s in steps)
                {
                    int at = (baseline.StartLagMs - f + s - 1) / s;
                    Console.Write("刻み{0}で{1}機目  ", s, at + 1);
                }
                Console.WriteLine();
            }
            Console.WriteLine();

            /* ---- 候補を絞って、本数を増やして確かめる ----
               上の表は各200本なので「終わらない走り」の数が当てにならない。
               **採る組だけ3倍の本数で回して、青天井が出ないことを確かめる。** */
            int fine = runs * 3;
            /* 案は「敵の速さ」だけでなく、Balance をまるごと触れる形にする。
               **40機を狙える難易度にすると、刻みだけでは1回が15分前後になる**
               （いまのイージーで1機あたり23秒。40機×23秒＝15分）。
               敵の耐久を下げれば **走りを伸ばさずに機数だけ増やせる**ので、そこも測る。 */
            /* **壁（下限）を難易度で分ける。**
               試遊で「イージー31機、ハードも31機」。31機はもう全員が壁の中で、
               旧イージーの壁3.5秒とハードの壁3.2秒は0.3秒しか違わなかった。
               **壁に着くまでの速さだけを分けても、壁の中では同じ難しさになる。** */
            var picks = new (string name, Action<Balance> set)[]
            {
                ("旧イージー 60/300",   b => { b.StepLagMs = 60; b.FloorLagMs = 300; }),
                ("いま 45/200",        b => { b.StepLagMs = 45; b.FloorLagMs = 200; }),
                ("50/450",             b => { b.StepLagMs = 50; b.FloorLagMs = 450; }),
                ("45/450",             b => { b.StepLagMs = 45; b.FloorLagMs = 450; }),
                ("50/400",             b => { b.StepLagMs = 50; b.FloorLagMs = 400; }),
                ("55/450",             b => { b.StepLagMs = 55; b.FloorLagMs = 450; }),
                ("60/450",             b => { b.StepLagMs = 60; b.FloorLagMs = 450; }),
                ("60/500",             b => { b.StepLagMs = 60; b.FloorLagMs = 500; }),
                ("70/450",             b => { b.StepLagMs = 70; b.FloorLagMs = 450; }),
                ("ノーマル 80/300",     b => { }),
                ("ハード 110/240",      b => { b.StepLagMs = 110; b.FloorLagMs = 240; }),
            };
            Console.WriteLine("【候補の確かめ】各" + fine + "本");
            Console.WriteLine("{0,-20} {1,7} {2,8} {3,7} {4,8} {5,8} {6,8} {7,10}",
                "案", "撃破", "生存秒", "最高", "20機到達", "30機到達", "40機到達", "終わらない");
            Console.WriteLine(new string('-', 86));
            foreach (var p in picks)
            {
                Balance bal = new Balance();
                p.set(bal);
                GameSimulator sim = new GameSimulator(bal);
                EndlessStats es = sim.RunEndless(new HandBot(Hand.FullHouse, 2000),
                                                 new RushBot(), humanLag, fine, seed++);
                /* 40機到達率を見たいので、配列の端をはみ出さないようにする。
                   HandsAtKill は「k機目に到達した走りの数」＝生存曲線。 */
                double R(int k) {
                    return (k < es.HandsAtKill.Length ? es.HandsAtKill[k] : 0) * 100.0 / fine;
                }
                Console.WriteLine("{0,-20} {1,6:F1}機 {2,7:F0}秒 {3,6}機 {4,7:F0}% {5,7:F0}% {6,7:F0}% {7,9}",
                    p.name + "(" + bal.FloorLagMs + "/" + bal.StepLagMs + "/HP" + bal.EnemyHp.ToString("F0") + ")",
                    es.AvgKills, es.AvgSec, es.BestKills,
                    R(20), R(30), R(40), es.NeverDied);
            }

            Console.WriteLine();
            Console.WriteLine("**選び方**：ノーマル（下限300/刻み80）を真ん中に置き、");
            Console.WriteLine("撃破数がはっきり上下する組を左右に取る。終わらない走りが出る段は採らない。");
            return 0;
        }

        /// <summary>
        /// 部位破壊の確率を振って、**出撃時の役の分布が実機と合うか**を見る。仕様書 9-6e。
        ///
        /// プロトタイプは当たれば **必ず** 壊す（v1.7 のまま）が、
        /// Core は 25%（v1.8 で決めた値）。**4倍ずれている。**
        /// あなたが触っているのは 100% のほうなので、実機の役の分布と突き合わせれば
        /// どちらが正しいかが決まる。
        ///
        /// ワンペアが 36% を占める原因が破壊にあるのかも、ここで同時に分かる。
        /// </summary>
        public static int RunStrip(string[] args)
        {
            int runs = 300;
            if (args.Length > 1) { int.TryParse(args[1], out runs); }

            // 実機3回目（36出撃）の実測。これに近い破壊率が「本当の値」。
            double[] real = { 36.1, 11.1, 19.4, 11.1, 5.6, 13.9, 2.8 };

            // ---- 較正の軸を「時間」から「手数」に変えた ----
            //
            // 組み立て10.2秒に合わせて lag=553ms にしたが、それだと **ボットが速く動ける**。
            // 1手 953ms なら 10.2秒で 10.7手。あなたは 7.6手（装着5＋引き直し2.6）。
            // **同じ時間でボットのほうが多く手を打てる＝実質的に賢い打ち手**になっていた。
            //
            // 実機3回目：288手（装着180＋引き直し94＋上書き14）／370.7秒 = **1手1.29秒**。
            // フリック400msを引くと lag ≒ 890ms。**既定の900がほぼ正解だった。**
            const int humanLag = 900;

            // ワンペアを撃つかどうかは「完成した機体をどれだけ握れるか」で決まる。
            // TargetBot は届くまで絶対に撃たないので、**ワンペアが1回も出ない**。
            // 実機の36%を再現できる粘りを探す。
            int[] holds = { 0, 1000, 2000, 4000, 8000 };
            double[] chances = { 0.25, 1.00 };

            Console.WriteLine("打ち手の粘り × 部位破壊の確率（各" + runs + "本、1手900ms）");
            Console.WriteLine("出撃時の役の分布を、実機3回目（36出撃）と突き合わせる");
            Console.WriteLine();
            Console.WriteLine("{0,6} {1,6} {2,7} {3,7} {4,7} {5,7} {6,7} {7,7} {8,7} | {9,6} {10,6}",
                "粘り", "破壊", "ワンペア", "ツーペア", "スリー", "フル", "プリズム", "フォー", "ピュア", "ズレ", "撃破");
            Console.WriteLine(new string('-', 100));

            Console.WriteLine("{0,6} {1,6} {2,6:F1}% {3,6:F1}% {4,6:F1}% {5,6:F1}% {6,6:F1}% {7,6:F1}% {8,6:F1}% | {9,6} {10,5:F1}機",
                "実機", "100%", real[0], real[1], real[2], real[3], real[4], real[5], real[6], "—", 8.0);

            int seed = 51000;
            foreach (int hold in holds)
            foreach (double ch in chances)
            {
                Balance bal = new Balance();
                bal.StripChance = ch;
                GameSimulator sim = new GameSimulator(bal);
                IBot human = new HandBot(Hand.FullHouse, hold);
                EndlessStats es = sim.RunEndless(human, new RushBot(), humanLag, runs, seed++);

                int total = 0;
                for (int i = 0; i < 7; i++) { total += es.Player.HandAtLaunchA[i]; }

                double[] got = new double[7];
                double diff = 0;
                for (int i = 0; i < 7; i++)
                {
                    got[i] = total == 0 ? 0 : es.Player.HandAtLaunchA[i] * 100.0 / total;
                    diff += Math.Abs(got[i] - real[i]);
                }

                Console.WriteLine("{0,5}ms {1,5:F0}% {2,6:F1}% {3,6:F1}% {4,6:F1}% {5,6:F1}% {6,6:F1}% {7,6:F1}% {8,6:F1}% | {9,6:F1} {10,5:F1}機",
                    hold, ch * 100, got[0], got[1], got[2], got[3], got[4], got[5], got[6], diff, es.AvgKills);
            }

            Console.WriteLine();
            Console.WriteLine("「ズレ」は実機との差の合計。小さいほど実機に近い。");
            Console.WriteLine("撃破数が粘りに対してどう動くかが、**ワンペアを撃つのが損かどうか** の答え。");

            // ---- 役の階段はエンドレスで機能しているか ----
            //
            // 粘るほど撃破が減るなら、**役を狙う意味が無い**ということになる。
            // 1v1（9-2）の「速攻 vs 役狙いが50:50」という基準は、
            // **決着1回の勝負**の話で、走り続けるエンドレスの話ではなかった。
            // 傾きを立てれば粘りが報われるようになるのかを見る。
            Console.WriteLine();
            Console.WriteLine("=== 役の傾きを立てたら、粘りは報われるか（撃破数）===");
            Console.WriteLine();
            Console.Write("{0,8}", "傾き");
            foreach (int hold in holds) { Console.Write("{0,9}", hold + "ms"); }
            Console.WriteLine("   {0,-10}", "最良の粘り");
            Console.WriteLine(new string('-', 68));

            foreach (double sc in new double[] { 2.5, 3.0, 4.0, 6.0 })
            {
                Console.Write("{0,7:F1}x", sc);
                double best = -1; int bestHold = 0;
                foreach (int hold in holds)
                {
                    Balance bal = new Balance();
                    bal.MulScale = sc;
                    GameSimulator sim = new GameSimulator(bal);
                    EndlessStats es = sim.RunEndless(
                        new HandBot(Hand.FullHouse, hold), new RushBot(), humanLag, runs, seed++);
                    Console.Write("{0,8:F1}機", es.AvgKills);
                    if (es.AvgKills > best) { best = es.AvgKills; bestHold = hold; }
                }
                Console.WriteLine("   {0,-10}", bestHold + "ms");
            }

            Console.WriteLine();
            Console.WriteLine("最良の粘りが 0ms のままなら、**エンドレスでは役を狙う価値が無い**。");
            return 0;
        }

        /// <summary>
        /// 実機で見つかった「塗り替え」戦法を測る。仕様書 9-5p。
        ///
        ///   埋まる札で一気に5枚そろえてから、引き直しを連打して狙った色の札を探し、
        ///   部位ごとに1回ずつ使える上書きで、機体をまるごと塗り替える。
        ///
        /// 見たいのは2つ。
        ///   (1) 本当にピュアカラーが出るのか（実機では21出撃中4回＝19%）
        ///   (2) **撃破数で得なのか**（実機では6機。前回の8機より減っている）
        /// </summary>
        public static int RunRepaint(string[] args)
        {
            int runs = 300;
            if (args.Length > 1) { int.TryParse(args[1], out runs); }

            const int humanLag = 900;

            var plans = new (string name, IBot bot)[]
            {
                ("すぐ撃つ",          new HandBot(Hand.FullHouse, 0)),
                ("最良の粘り2秒",      new HandBot(Hand.FullHouse, 2000)),
                ("あと1色だけ 3秒",    new RepaintBot(3000, true)),
                ("あと1色だけ 6秒",    new RepaintBot(6000, true)),
                ("あと1色だけ 12秒",   new RepaintBot(12000, true)),
                ("全部塗り替え 6秒",   new RepaintBot(6000)),
                ("全部塗り替え 12秒",  new RepaintBot(12000)),
                ("全部塗り替え 20秒",  new RepaintBot(20000)),
                ("ピュア狙い(粘る)",   new TargetBot(Hand.PureColor)),
            };

            Console.WriteLine("塗り替え戦法を測る（各" + runs + "本、1手900ms）");
            Console.WriteLine("実機の実測: 6機/290.7秒、21出撃中ピュアカラー4回(19%)、引き直し93枚");
            Console.WriteLine();
            Console.WriteLine("{0,-18} {1,7} {2,8} {3,8} {4,8} {5,8} {6,8}",
                "打ち方", "撃破", "生存秒", "出撃", "ピュア%", "フォー%", "ワンペア%");
            Console.WriteLine(new string('-', 74));

            int seed = 61000;
            foreach (var p in plans)
            {
                Balance bal = new Balance();
                GameSimulator sim = new GameSimulator(bal);
                EndlessStats es = sim.RunEndless(p.bot, new RushBot(), humanLag, runs, seed++);

                int total = 0;
                for (int i = 0; i < 7; i++) { total += es.Player.HandAtLaunchA[i]; }
                double pure = total == 0 ? 0 : es.Player.HandAtLaunchA[(int)Hand.PureColor] * 100.0 / total;
                double four = total == 0 ? 0 : es.Player.HandAtLaunchA[(int)Hand.FourOfAKind] * 100.0 / total;
                double one  = total == 0 ? 0 : es.Player.HandAtLaunchA[(int)Hand.OnePair] * 100.0 / total;

                Console.WriteLine("{0,-18} {1,6:F1}機 {2,7:F1}秒 {3,7:F1}回 {4,7:F1}% {5,7:F1}% {6,7:F1}%",
                    p.name, es.AvgKills, es.AvgSec, total / (double)runs, pure, four, one);
            }

            // ---- 部位破壊が塗り替えをどれだけ潰しているか ----
            //
            // 完成した機体を握って塗り替えている間、相手の攻撃が当たると部位が飛ぶ。
            // フォーカードが崩れれば、そこまでの上書きは無駄になる。
            // **破壊を切って比べれば、その分が見える。**
            Console.WriteLine();
            Console.WriteLine("=== 部位破壊を切ると、どれだけ通るようになるか ===");
            Console.WriteLine();
            Console.WriteLine("{0,-18} {1,17} {2,17}", "打ち方", "破壊あり(現行)", "破壊なし");
            Console.WriteLine("{0,-18} {1,8} {2,8} {3,8} {4,8}", "", "撃破", "ピュア%", "撃破", "ピュア%");
            Console.WriteLine(new string('-', 56));

            foreach (var p in plans)
            {
                var row = new double[4];
                for (int k = 0; k < 2; k++)
                {
                    Balance bal = new Balance();
                    if (k == 1) { bal.StripChance = 0.0; }
                    GameSimulator sim = new GameSimulator(bal);
                    EndlessStats es = sim.RunEndless(p.bot, new RushBot(), humanLag, runs, seed++);
                    int total = 0;
                    for (int i = 0; i < 7; i++) { total += es.Player.HandAtLaunchA[i]; }
                    row[k*2]     = es.AvgKills;
                    row[k*2 + 1] = total == 0 ? 0 : es.Player.HandAtLaunchA[(int)Hand.PureColor] * 100.0 / total;
                }
                Console.WriteLine("{0,-18} {1,7:F1}機 {2,7:F1}% {3,7:F1}機 {4,7:F1}%",
                    p.name, row[0], row[1], row[2], row[3]);
            }

            Console.WriteLine();
            Console.WriteLine("撃破数が「すぐ撃つ」を上回れば、塗り替えは戦法として得。");
            return 0;
        }

        /// <summary>第3引数で傾きを指定できるようにする。省略時は既定値。</summary>
        private static double MulFor(string[] args, double fallback)
        {
            double v;
            if (args.Length > 2 && double.TryParse(args[2], out v)) { return v; }
            return fallback;
        }

        public static int RunSubColor(string[] args)
        {
            int matches = 600;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            double[] subs = { 0.0, 0.5, 1.0, 1.5 };

            // 配分の案を2つ並べる。列は [追加ダメージ, 回復, シールド]。
            //
            // 甲：当初案（赤＝攻撃、紫＝攻撃とシールド半々）
            //     → **追加ダメージが役の階段を壊す。**
            //        ツーペア(赤)146.6 + 115×0.5 = 204 で、スリーカード最小 157 を超える。
            //        ツーペア→スリーカードの境目は余裕が 10 しかないので、
            //        ダメージを少しでも混ぜたら必ず食い破る。
            //
            // 乙：ダメージ抜き（回復とシールドだけに配る）
            //     → 威力の軸に触らないので、階段は絶対に壊れない。
            double[,] mixA =
            {
                { 1.0, 0.0, 0.0 },   // 赤 攻撃
                { 0.0, 1.0, 0.0 },   // 青 回復
                { 0.0, 0.5, 0.5 },   // 黄 半々
                { 0.0, 0.0, 1.0 },   // 緑 シールド
                { 0.5, 0.0, 0.5 },   // 紫 攻撃とシールド
            };
            double[,] mixB =
            {
                { 0.0, 0.0, 1.0 },   // 赤 シールド
                { 0.0, 1.0, 0.0 },   // 青 回復
                { 0.0, 0.5, 0.5 },   // 黄 半々
                { 0.0, 0.3, 0.7 },   // 緑 シールド寄り
                { 0.0, 0.7, 0.3 },   // 紫 回復寄り
            };
            // 丙：シールドのみ。色の差は無いが、**試合が伸びる原因が回復かシールドか**を切り分ける。
            // 回復は与えたダメージを打ち消して決着を戻すが、
            // シールドは上限があり時間で消えるので、伸びかたが違うはず。
            double[,] mixC =
            {
                { 0.0, 0.0, 1.0 },
                { 0.0, 0.0, 1.0 },
                { 0.0, 0.0, 1.0 },
                { 0.0, 0.0, 1.0 },
                { 0.0, 0.0, 1.0 },
            };

            Console.WriteLine("副色の効果の強さを振る（各" + matches + "戦 × 2対戦、傾き" + MulFor(args, 2.5).ToString("F1") + "）");
            Console.WriteLine("目標: フルハウス狙いが 対速攻で 45〜55%、試合時間が伸びないこと");
            Console.WriteLine("甲=当初案（赤が追加ダメージ） / 乙=ダメージ抜き / 丙=シールドのみ（原因の切り分け）");
            Console.WriteLine();
            Console.WriteLine("{0,4} {1,6} | {2,10} {3,10} | {4,8} {5,8} {6,8} {7,8}",
                "配分", "副色", "フル狙い", "ピュア狙い", "試合秒", "副色回数", "回復量", "吸収量");
            Console.WriteLine(new string('-', 82));

            int seed = 21000;
            for (int m = 0; m < 3; m++)
            {
                foreach (double sv in subs)
                {
                    Balance bal = new Balance();
                    bal.MulScale = MulFor(args, 2.5);
                    bal.SubColorScale = sv;
                    bal.SubColorMix = m == 0 ? mixA : (m == 1 ? mixB : mixC);
                    GameSimulator sim = new GameSimulator(bal);

                    SimStats f = sim.Run(new TargetBot(Hand.FullHouse), new RushBot(), matches, seed++);
                    SimStats p = sim.Run(new TargetBot(Hand.PureColor), new RushBot(), matches, seed++);

                    Console.WriteLine("{0,4} {1,5:F1}x | {2,9:F1}% {3,9:F1}% | {4,7:F1}秒 {5,8:F1} {6,8:F0} {7,8:F0}",
                        m == 0 ? "甲" : (m == 1 ? "乙" : "丙"), sv, f.WinRateA, p.WinRateA, f.AvgDurationSec,
                        f.SubColorHits / 2.0 / matches, f.SubHeal / 2.0 / matches, f.SubAbsorbed / 2.0 / matches);
                }
                if (m < 2) { Console.WriteLine(); }
            }

            Console.WriteLine();
            Console.WriteLine("勝率は **役狙い側**。50%に近いほど釣り合っている。");
            Console.WriteLine("試合秒が右に行くほど伸びるなら、回復が決着を先延ばしにしている。");
            return 0;
        }

        /// <summary>
        /// 「壁のあとに終わりが来るか」を、**打ち手の速さを変えながら**測る（仕様書 9-6n）。
        ///
        /// きっかけは実機の報告 ―― **イージーで92機。**
        /// 既存の diff / run は打ち手を1手900ms（実機の平均）に固定しているので、
        /// **速い人が壁の向こうでどうなるか**が測れなかった。
        /// ここでは1手のコストだけを動かし、制限時間も60分まで伸ばす。
        ///   dotnet run -- wall [本数]
        /// </summary>
        public static int RunWall(string[] args)
        {
            int runs = 120;
            if (args.Length > 1) { int.TryParse(args[1], out runs); }
            int bot = 0;
            if (args.Length > 2) { int.TryParse(args[2], out bot); }

            // いまの3段（playtest.html の DIFFS と同じ値）
            var diffs = new (string name, int floor, int step)[]
            {
                ("イージー", 450,  50),
                ("ノーマル", 300,  80),
                ("ハード",   240, 110),
            };
            // 1手のコスト。900 が実機の平均（9-6e）。下へ行くほど速い打ち手。
            int[] lags = { 400, 250, 150, 50, 0 };

            const int limitMs = 3600000;   // 60分。15分では「終わらない」が測れない

            Console.WriteLine("壁の向こうに終わりが来るか（各" + runs + "本・制限60分）");
            Console.WriteLine("打ち手は " + BotName(bot) + "。1手のコストだけを変える。");
            Console.WriteLine("**60分率が0でない＝その速さの人は倒れない。**");
            Console.WriteLine();
            Console.WriteLine("{0,-9}{1,7}{2,8}{3,9}{4,8}{5,9}{6,9}", "難易度", "1手ms", "組立秒", "平均撃破", "最高", "平均分", "60分率");
            Console.WriteLine(new string('-', 59));

            int seed = 91000;
            foreach (var d in diffs)
            {
                foreach (int lag in lags)
                {
                    Balance bal = new Balance();
                    bal.FloorLagMs = d.floor;
                    bal.StepLagMs = d.step;
                    bal.EndlessLimitMs = limitMs;
                    GameSimulator sim = new GameSimulator(bal);
                    EndlessStats es = sim.RunEndless(BotOf(bot), new RushBot(), lag, runs, seed++);
                    Console.WriteLine("{0,-9}{1,7}{2,8:F1}{3,9:F1}{4,8}{5,8:F1}{6,8:F0}%",
                        d.name, lag, es.AvgBuildSec, es.AvgKills, es.BestKills,
                        es.AvgSec / 60.0, es.NeverDied * 100.0 / runs);
                }
                Console.WriteLine();
            }

            Console.WriteLine("平均分が制限（60分）に張り付いたら、その行は **終わらない走り** です。");
            Console.WriteLine("最高撃破が本数を増やすたびに伸び続ける行も同じ意味になります。");
            return 0;
        }

        /// <summary>
        /// 案A（壁の先の二段目の坂）・案B（回復の減衰）・案C（敵の耐久増）を、
        /// **同じ打ち手**で並べて測る（仕様書 9-6o）。
        ///
        /// 打ち手は実機の要望どおり **組み立て平均9秒**（1手250ms・wall で較正した値）。
        /// 狙いは「頑張ったとき」の到達点で、イージー60／ノーマル40／ハード30。
        ///   dotnet run -- tune [本数]
        /// </summary>
        public static int RunTune(string[] args)
        {
            int runs = 30;
            if (args.Length > 1) { int.TryParse(args[1], out runs); }
            /* 打ち手の1手のコスト。**ここを動かすと全部の行が動く。**
               250 = 組立9.0秒（頑張ったとき）／450 = 組立10.7秒（実機の92機の走り）。
               wall コマンドで較正した値。 */
            int humanLag = 250;
            if (args.Length > 2) { int.TryParse(args[2], out humanLag); }
            int bot = 0;
            if (args.Length > 3) { int.TryParse(args[3], out bot); }
            // 0=全部 1=A 2=B 3=C。**Cだけを広く振りたい**ときに使う（9-6o）
            int only = 0;
            if (args.Length > 4) { int.TryParse(args[4], out only); }
            const int limitMs = 3600000;   // 60分

            // 名前 / 下限 / 刻み / 壁に着く撃破数（(2000-下限)÷刻み）
            var diffs = new (string name, int floor, int step, int wall)[]
            {
                ("イージー", 450,  50, 31),
                ("ノーマル", 300,  80, 22),
                ("ハード",   240, 110, 16),
            };

            var plans = new List<(string label, Action<Balance> set)>();
            plans.Add(("現状（なにもしない）", b => { }));
            if (only == 0 || only == 1)
            {
                foreach (int s in new[] { 10, 20, 30, 50 })
                {
                    int ss = s;
                    plans.Add(("A 二段目 " + ss + "ms/機", b => { b.Slope2StepMs = ss; }));
                }
            }
            if (only == 0 || only == 2)
            {
                foreach (double d in new[] { 0.99, 0.98, 0.96, 0.94 })
                {
                    double dd = d;
                    plans.Add(("B 回復 ×" + dd.ToString("F2") + "/機", b => { b.HealDecay = dd; }));
                }
            }
            if (only == 5)
            {
                // 採用案だけを本数を増やして確かめる（9-6r）。30本では最高値が振れる
                plans.Add(("採用案 B×0.995 + C+10",
                    b => { b.HealDecay = 0.995; b.EnemyHpGrowth = 10; }));
            }
            if (only == 4)
            {
                /* B と C を **どちらも弱めにして重ねる**（9-6o）。
                   片方だけを強くすると、B は3段の差を潰し、C は上達の伸びを潰す。
                   薄く2枚重ねれば、どちらの副作用も浅いまま効くはず ―― を測る。 */
                foreach (double dd0 in new[] { 0.995, 0.99, 0.985 })
                {
                    foreach (int gg0 in new[] { 5, 10, 15 })
                    {
                        double dd = dd0; int gg = gg0;
                        plans.Add(("B×" + dd.ToString("F3") + " + C+" + gg,
                            b => { b.HealDecay = dd; b.EnemyHpGrowth = gg; }));
                    }
                }
                // 比較のための単独。**同じ本数・同じ種で並べないと比べられない。**
                plans.Add(("（参考）B×0.98 だけ", b => { b.HealDecay = 0.98; }));
                plans.Add(("（参考）C+10 だけ",   b => { b.EnemyHpGrowth = 10; }));
            }
            if (only == 0 || only == 3)
            {
                /* **上のほうまで振る。** 5秒を切る打ち手には +40 でも足りない（9-6o）。 */
                int[] gs = (only == 3) ? new[] { 20, 40, 60, 80, 120, 160, 220 } : new[] { 5, 10, 20, 40 };
                foreach (int g in gs)
                {
                    int gg = g;
                    plans.Add(("C 敵HP +" + gg + "/機", b => { b.EnemyHpGrowth = gg; }));
                }
            }

            Console.WriteLine("A・B・C を同じ打ち手で比べる（各" + runs + "本・制限60分）");
            Console.WriteLine("打ち手は " + BotName(bot) + "・1手" + humanLag + "ms（既定の打ち手なら 250≒組立9.0秒 ／ 450≒組立10.7秒）。");
            Console.WriteLine("狙い: イージー60 ／ ノーマル40 ／ ハード30（頑張ったときの到達点）");
            Console.WriteLine();

            int seed = 93000;
            foreach (var d in diffs)
            {
                Console.WriteLine("■ " + d.name + "（下限" + d.floor + " / 刻み" + d.step
                                  + " / 壁は" + d.wall + "機目）");
                Console.WriteLine("{0,-22}{1,8}{2,8}{3,8}{4,8}{5,8}",
                    "案", "平均", "最高", "組立秒", "平均分", "60分率");
                Console.WriteLine(new string('-', 62));
                foreach (var p in plans)
                {
                    Balance bal = new Balance();
                    bal.FloorLagMs = d.floor;
                    bal.StepLagMs = d.step;
                    bal.EndlessLimitMs = limitMs;
                    // 二段目は **その難易度の壁から** 始める。平地を作らないため。
                    bal.Slope2AtKills = d.wall;
                    p.set(bal);
                    GameSimulator sim = new GameSimulator(bal);
                    EndlessStats es = sim.RunEndless(BotOf(bot), new RushBot(), humanLag, runs, seed++);
                    Console.WriteLine("{0,-22}{1,8:F1}{2,8}{3,8:F1}{4,8:F1}{5,7:F0}%",
                        p.label, es.AvgKills, es.BestKills, es.AvgBuildSec,
                        es.AvgSec / 60.0, es.NeverDied * 100.0 / runs);
                }
                Console.WriteLine();
            }
            Console.WriteLine("**60分率が0でない行は、その速さの人が倒れない**＝採ってはいけない。");
            Console.WriteLine("平均分が長すぎる行も避ける。1本が30分では順位表が根気比べになる。");
            return 0;
        }

        /// <summary>
        /// 打ち手の型を番号で選ぶ。**wall と tune で同じ番号を使う。**
        /// 番号がずれると、較正した表と本測定の表が別人のものになる（9-2d の轍）。
        ///   0 = 役狙い・フルハウス・粘り2000ms（実機の平均に合わせた既定）
        ///   1 = 役狙い・フルハウス・粘り800ms（粘らない上手い人）
        ///   2 = 役狙い・ツーペア・粘り400ms（そこそこの役で即撃つ）
        ///   3 = 速攻（組み上がったら即撃つ。**いちばん速い**）
        /// </summary>
        private static IBot BotOf(int i)
        {
            if (i == 1) { return new HandBot(Hand.FullHouse, 800); }
            if (i == 2) { return new HandBot(Hand.TwoPair, 400); }
            if (i == 3) { return new RushBot(); }
            return new HandBot(Hand.FullHouse, 2000);
        }
        private static string BotName(int i)
        {
            if (i == 1) { return "役狙い粘800"; }
            if (i == 2) { return "2ペア粘400"; }
            if (i == 3) { return "速攻"; }
            return "役狙い粘2000";
        }

        /// <summary>
        /// **撃破数の区間ごとの組み立て時間**を出す（仕様書 9-6o）。
        ///
        /// きっかけは実機の問い ―― 「全体の平均ではなく、60機以降の平均は幾ら？」
        /// 順位表に載る avgMs は **走り1本を通した平均**で、序盤と終盤が混ざっている。
        /// 終盤は相手が速く、部位も壊されるので、同じ人でも組み立ては延びる。
        ///   dotnet run -- curve [本数] [1手ms] [打ち手番号] [難易度0-2]
        /// </summary>
        public static int RunCurve(string[] args)
        {
            int runs = 40;
            if (args.Length > 1) { int.TryParse(args[1], out runs); }
            int humanLag = 450;                     // 既定は実機の92機の走り（組立10.7秒）
            if (args.Length > 2) { int.TryParse(args[2], out humanLag); }
            int bot = 0;
            if (args.Length > 3) { int.TryParse(args[3], out bot); }
            int di = 0;
            if (args.Length > 4) { int.TryParse(args[4], out di); }

            var diffs = new (string name, int floor, int step)[]
            {
                ("イージー", 450,  50),
                ("ノーマル", 300,  80),
                ("ハード",   240, 110),
            };
            if (di < 0 || di > 2) { di = 0; }
            var d = diffs[di];

            Balance bal = new Balance();
            bal.FloorLagMs = d.floor;
            bal.StepLagMs = d.step;
            bal.EndlessLimitMs = 3600000;
            GameSimulator sim = new GameSimulator(bal);
            EndlessStats es = sim.RunEndless(BotOf(bot), new RushBot(), humanLag, runs, 95000);

            Console.WriteLine(d.name + "・現状のまま／" + BotName(bot) + "・1手" + humanLag + "ms（"
                              + runs + "本・制限60分）");
            Console.WriteLine("平均撃破 " + es.AvgKills.ToString("F1")
                              + " ／ 最高 " + es.BestKills
                              + " ／ 走り全体の組立平均 " + es.AvgBuildSec.ToString("F1") + "秒");
            Console.WriteLine();
            Console.WriteLine("{0,-12}{1,10}{2,12}", "撃破の区間", "出撃数", "組立平均秒");
            Console.WriteLine(new string('-', 34));
            for (int b = 0; b < EndlessStats.Buckets; b++)
            {
                if (es.LaunchesByBucket[b] == 0) { continue; }
                int lo = b * EndlessStats.BucketSize;
                string label = (b == EndlessStats.Buckets - 1)
                    ? (lo + "機以上") : (lo + "〜" + (lo + EndlessStats.BucketSize - 1) + "機");
                Console.WriteLine("{0,-12}{1,10}{2,12:F2}",
                    label, es.LaunchesByBucket[b], es.AvgBuildSecAt(b));
            }
            Console.WriteLine();
            foreach (int from in new[] { 0, 20, 40, 60, 80, 100 })
            {
                double v = es.AvgBuildSecFrom(from);
                if (v <= 0) { continue; }
                Console.WriteLine("{0,3}機以降だけの組立平均: {1:F2}秒", from, v);
            }
            Console.WriteLine();
            Console.WriteLine("**順位表の avgMs はいちばん上（0機以降＝全体）と同じ意味です。**");
            return 0;
        }
    }
}
