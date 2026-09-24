using System;

namespace RoboSpeed.Core
{
    /// <summary>
    /// 役判定。仕様書 4-1。
    /// 5枚のメーカーの「色の枚数分布」だけで決まる。スロットが何かは関係しない。
    /// Unity に依存しないので、コンソールから1000万回でも回せる。
    /// </summary>
    public static class HandEvaluator
    {
        /// <summary>
        /// 5つのメーカーから役を判定する。
        /// 分布（降順の枚数）で分岐するだけ。
        /// </summary>
        public static Hand Evaluate(Manufacturer[] makers)
        {
            if (makers == null || makers.Length != Counts.Slots)
            {
                throw new ArgumentException("役の判定には5枚ちょうどが要る", "makers");
            }

            // 各メーカーが何枚使われているかを数える
            int[] counts = new int[Counts.Manufacturers];
            for (int i = 0; i < makers.Length; i++)
            {
                counts[(int)makers[i]]++;
            }

            // 最大枚数と、2番目に多い枚数、使われた色数を求める
            int max = 0;
            int second = 0;
            int distinct = 0;
            for (int i = 0; i < counts.Length; i++)
            {
                int c = counts[i];
                if (c > 0) { distinct++; }
                if (c > max) { second = max; max = c; }
                else if (c > second) { second = c; }
            }

            return FromShape(max, second, distinct);
        }

        /// <summary>
        /// 分布の形から役を決める。
        /// 5枚固定なので、最大枚数と2番目の枚数だけで一意に定まる。
        /// </summary>
        public static Hand FromShape(int max, int second, int distinct)
        {
            if (max == 5) { return Hand.PureColor; }        // 5
            if (max == 4) { return Hand.FourOfAKind; }      // 4-1
            if (max == 3)
            {
                return second == 2 ? Hand.FullHouse         // 3-2
                                   : Hand.ThreeOfAKind;     // 3-1-1
            }
            if (max == 2)
            {
                return second == 2 ? Hand.TwoPair           // 2-2-1
                                   : Hand.OnePair;          // 2-1-1-1
            }
            return Hand.Prism;                              // 1-1-1-1-1
        }

        /// <summary>
        /// 使われたメーカーの数。必殺技の選択肢の数になる。仕様書 6-2c。
        /// ピュアカラー=1、プリズム=5。
        /// </summary>
        public static int DistinctMakers(Manufacturer[] makers)
        {
            bool[] seen = new bool[Counts.Manufacturers];
            int n = 0;
            for (int i = 0; i < makers.Length; i++)
            {
                int m = (int)makers[i];
                if (!seen[m]) { seen[m] = true; n++; }
            }
            return n;
        }

        /// <summary>表示用の名前。</summary>
        public static string NameOf(Hand hand)
        {
            switch (hand)
            {
                case Hand.PureColor: return "ピュアカラー";
                case Hand.FourOfAKind: return "フォーカード";
                case Hand.Prism: return "プリズム";
                case Hand.FullHouse: return "フルハウス";
                case Hand.ThreeOfAKind: return "スリーカード";
                case Hand.TwoPair: return "ツーペア";
                case Hand.OnePair: return "ワンペア";
                default: return hand.ToString();
            }
        }
    }
}
