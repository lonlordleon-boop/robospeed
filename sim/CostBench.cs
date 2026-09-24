using System;
using RoboSpeed.Core;

namespace RoboSpeed.Sim
{
    /// <summary>
    /// 各役に到達するまでの実コストを、**対戦の中で**測る。
    ///
    /// 相手が居ない状態で測ると、好きなだけパージして待てるため
    /// どの役も同じくらい簡単になってしまい、意味のある差が出ない。
    /// 実戦ではカードを奪われ、妨害で違う色を差し込まれるので、
    /// 選り好みする戦術ほどコストが跳ね上がる。そこを測る。
    /// </summary>
    public static class CostBench
    {
        public static int Run(string[] args)
        {
            int matches = 3000;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            Balance bal = new Balance();
            GameSimulator sim = new GameSimulator(bal);

            Hand[] targets =
            {
                Hand.OnePair, Hand.TwoPair, Hand.ThreeOfAKind,
                Hand.FullHouse, Hand.Prism, Hand.FourOfAKind, Hand.PureColor,
            };

            Console.WriteLine("役ごとの実コスト（対戦の中で計測・相手は速攻ボット）");
            Console.WriteLine("各" + matches + "戦。狙う役ごとに専用ボットを立てて測る。");
            Console.WriteLine();
            Console.WriteLine("{0,-12} {1,9} {2,9} {3,9} {4,9}  {5}",
                "狙う役", "組立て秒", "平均倍率", "実効率", "勝率", "実際に出た役");
            Console.WriteLine(new string('-', 86));

            for (int t = 0; t < targets.Length; t++)
            {
                Hand target = targets[t];
                SimStats st = sim.Run(new TargetBot(target), new RushBot(), matches, 5500 + t);

                // 相手（速攻ボット）の出撃が混ざらないよう、A側だけを見る
                int total = st.LaunchesAOnly;
                if (total == 0) { continue; }

                long totalMs = 0;
                double mulSum = 0;
                for (int i = 0; i < 7; i++)
                {
                    totalMs += st.BuildMsByHandA[i];
                    mulSum += st.HandAtLaunchA[i] * bal.MultiplierOf((Hand)i);
                }

                double sec = totalMs / 1000.0 / total;
                double avgMul = mulSum / total;
                double eff = sec <= 0 ? 0 : avgMul / sec;

                // 実際に出撃した役のうち、多い順に2つ
                int i1 = 0, i2 = -1;
                for (int i = 1; i < 7; i++) { if (st.HandAtLaunchA[i] > st.HandAtLaunchA[i1]) { i1 = i; } }
                for (int i = 0; i < 7; i++)
                {
                    if (i == i1) { continue; }
                    if (i2 < 0 || st.HandAtLaunchA[i] > st.HandAtLaunchA[i2]) { i2 = i; }
                }
                string mix = string.Format("{0} {1:F0}% / {2} {3:F0}%",
                    HandEvaluator.NameOf((Hand)i1), st.HandAtLaunchA[i1] * 100.0 / total,
                    HandEvaluator.NameOf((Hand)i2), st.HandAtLaunchA[i2] * 100.0 / total);

                Console.WriteLine("{0,-12} {1,8:F2}秒 {2,8:F2}x {3,8:F2} {4,8:F1}%  {5}",
                    HandEvaluator.NameOf(target), sec, avgMul, eff, st.WinRateA, mix);
            }

            Console.WriteLine();
            Console.WriteLine("実効率 = 平均倍率 ÷ 平均組立て秒。1回の出撃あたりの「秒あたり打撃力」。");
            Console.WriteLine("これが揃っていれば、どの戦術を選んでも同じ効率になる。");
            Console.WriteLine("（勝率は対 速攻ボット）");
            return 0;
        }

        /// <summary>
        /// 倍率全体の傾きを振る。
        /// 組立て時間は 8.0→13.1秒（1.6倍）しか伸びないのに倍率が 1.0→7.0（7倍）開いていたため、
        /// 粘る打ち手が一方的に強くなっていた。傾きを下げて釣り合う点を探す。
        /// </summary>
        public static int RunScale(string[] args)
        {
            int matches = 2000;
            if (args.Length > 1) { int.TryParse(args[1], out matches); }

            double[] scales = { 0.70, 0.80, 0.85, 0.90, 0.95 };

            Console.WriteLine("倍率の傾きを振る（各" + matches + "戦 × 3対戦）");
            Console.WriteLine("目標: 粘る打ち手（フルハウス／ピュアカラー狙い）が対 速攻で 45〜55%");
            Console.WriteLine();
            Console.WriteLine("{0,6} | {1,10} {2,10} {3,10} | {4,10}",
                "傾き", "スリー狙い", "フル狙い", "ピュア狙い", "ピュア倍率");
            Console.WriteLine(new string('-', 60));

            int seed = 8800;
            foreach (double sc in scales)
            {
                Balance bal = new Balance();
                // 現在の表は「素の値から1.0を引いて3倍」した状態なので、いったん戻してから掛け直す
                for (int i = 0; i < bal.HandMultiplier.Length; i++)
                {
                    double raw = 1.0 + (bal.HandMultiplier[i] - 1.0) / 3.0;
                    bal.HandMultiplier[i] = 1.0 + (raw - 1.0) * sc;
                }

                GameSimulator sim = new GameSimulator(bal);
                double w3 = sim.Run(new TargetBot(Hand.ThreeOfAKind), new RushBot(), matches, seed++).WinRateA;
                double wF = sim.Run(new TargetBot(Hand.FullHouse), new RushBot(), matches, seed++).WinRateA;
                double wP = sim.Run(new TargetBot(Hand.PureColor), new RushBot(), matches, seed++).WinRateA;

                Console.WriteLine("{0,6:F2} | {1,9:F1}% {2,9:F1}% {3,9:F1}% | {4,9:F2}x",
                    sc, w3, wF, wP, bal.MultiplierOf(Hand.PureColor));
            }

            Console.WriteLine();
            Console.WriteLine("（傾き3.00 が現在の設定。粘る打ち手が強すぎることが分かっている）");
            return 0;
        }
    }
}
