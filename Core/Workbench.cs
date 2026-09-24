using System;

namespace RoboSpeed.Core
{
    /// <summary>
    /// 作業台。5スロット。仕様書 3-4／3-5／3-6。
    /// 機体は一度切りなので、出撃・ガードのたびに Clear() で全損させる。
    /// </summary>
    public class Workbench
    {
        private readonly Manufacturer[] _slot = new Manufacturer[Counts.Slots];
        private readonly bool[] _filled = new bool[Counts.Slots];
        private readonly bool[] _overwritten = new bool[Counts.Slots];

        public bool IsFilled(PartSlot slot) { return _filled[(int)slot]; }
        public Manufacturer MakerAt(PartSlot slot) { return _slot[(int)slot]; }

        /// <summary>同一スロットの上書きは1回まで。仕様書 3-6。</summary>
        public bool CanOverwrite(PartSlot slot)
        {
            return _filled[(int)slot] && !_overwritten[(int)slot];
        }

        /// <summary>
        /// その札が、いまの作業台では **どうやっても使えない** か。仕様書 9-5r。
        /// 部位が埋まっていて、かつ上書きも効かない（同じ色／もう上書き済み）。
        /// v1.10 から、この札は **配らない**（錠前を出すのをやめた）。
        /// </summary>
        public bool IsDead(MechaCard card)
        {
            int i = (int)card.Slot;
            if (!_filled[i]) { return false; }
            if (_overwritten[i]) { return true; }
            return _slot[i] == card.Maker;
        }

        /// <summary>
        /// いまの作業台に対して、使える札が25種のうち1枚でもあるか。仕様書 9-5r。
        /// 全部埋まって全部上書き済みのときだけ false。そこは強制出撃になる。
        /// </summary>
        public bool AnyPlayable()
        {
            for (int i = 0; i < Counts.Slots; i++)
            {
                if (!_filled[i] || !_overwritten[i]) { return true; }
            }
            return false;
        }

        public int FilledCount
        {
            get
            {
                int n = 0;
                for (int i = 0; i < _filled.Length; i++) { if (_filled[i]) { n++; } }
                return n;
            }
        }

        public bool IsComplete { get { return FilledCount == Counts.Slots; } }

        /// <summary>空きスロットに装着する。埋まっていれば false（上書きは Overwrite で）。</summary>
        public bool Install(MechaCard card)
        {
            int i = (int)card.Slot;
            if (_filled[i]) { return false; }
            _slot[i] = card.Maker;
            _filled[i] = true;
            return true;
        }

        /// <summary>
        /// 上書き。既存を排除して差し替える。
        /// 排除されたカードは捨て札へ回すので、呼び出し側が受け取る。
        /// </summary>
        public bool Overwrite(MechaCard card, out MechaCard removed)
        {
            int i = (int)card.Slot;
            removed = default(MechaCard);
            if (!CanOverwrite(card.Slot)) { return false; }
            removed = new MechaCard(_slot[i], card.Slot);
            _slot[i] = card.Maker;
            _overwritten[i] = true;
            return true;
        }

        /// <summary>
        /// 現在の役。未完成なら null 相当として OnePair 扱いにはせず、
        /// 呼び出し側が IsComplete を見て判断すること。
        /// </summary>
        public Hand EvaluateHand()
        {
            if (!IsComplete) { throw new InvalidOperationException("未完成の機体には役が無い"); }
            return HandEvaluator.Evaluate(_slot);
        }

        /// <summary>使われているメーカーの数＝必殺技の選択肢の数。仕様書 6-2c。</summary>
        public int DistinctMakers()
        {
            if (!IsComplete) { throw new InvalidOperationException("未完成の機体には必殺技が無い"); }
            return HandEvaluator.DistinctMakers(_slot);
        }

        /// <summary>装着済みメーカーの内訳。ボットの判断に使う。</summary>
        public void CountMakers(int[] into)
        {
            Array.Clear(into, 0, into.Length);
            for (int i = 0; i < _filled.Length; i++)
            {
                if (_filled[i]) { into[(int)_slot[i]]++; }
            }
        }

        /// <summary>
        /// 全損。出撃したとき、ガードで受け止めたとき。仕様書 6-3。
        /// 載っていたカードは捨て札へ回す。
        /// </summary>
        public void Clear(SupplyLine line)
        {
            for (int i = 0; i < _filled.Length; i++)
            {
                if (_filled[i] && line != null)
                {
                    line.Discard(new MechaCard(_slot[i], (PartSlot)i));
                }
                _filled[i] = false;
                _overwritten[i] = false;
            }
        }
    }
}
