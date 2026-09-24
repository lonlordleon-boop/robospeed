using System;

namespace RoboSpeed.Core
{
    public enum ActionKind
    {
        Wait,
        /// <summary>共有ラインの1枚を自分の作業台へ。</summary>
        TakeToSelf,
        /// <summary>共有ラインの1枚で自分の装着済みスロットを上書き。</summary>
        Overwrite,
        /// <summary>パージ。手札4枚をまとめて捨てて引き直す（v1.10 で復活・9-5r）。</summary>
        Purge,
        /// <summary>出撃。機体は全損する。</summary>
        Launch,
        /// <summary>ガード。受け止めれば機体は全損する。</summary>
        Guard,
    }

    public struct BotAction
    {
        public ActionKind Kind;
        public int LineIndex;
        public int HoldMs;

        public static BotAction Of(ActionKind kind, int lineIndex)
        {
            BotAction a = new BotAction();
            a.Kind = kind;
            a.LineIndex = lineIndex;
            return a;
        }

        public static BotAction GuardFor(int holdMs)
        {
            BotAction a = new BotAction();
            a.Kind = ActionKind.Guard;
            a.HoldMs = holdMs;
            return a;
        }
    }

    /// <summary>ボットに見せる盤面。相手の伏せコアは見えない前提で扱う。</summary>
    public class BotView
    {
        public Workbench Self;
        public Workbench Opponent;
        public SupplyLine Line;
        public double SelfHpRatio;
        public double OpponentHpRatio;
        public int NowMs;
        /// <summary>自分の機体が完成してからの経過。溜めすぎ防止に使う。</summary>
        public int HeldMs;
        /// <summary>今の機体で既に使った上書きの回数。組み直すと0に戻る。</summary>
        public int OverwritesUsed;
        /// <summary>
        /// 今の機体を組み始めてから引き直した枚数。組み直すと0に戻る。
        /// 人間は何十回も引き直さない。**選り好みに上限を持たせる**ために要る。
        /// </summary>
        public int DiscardsThisBuild;
        public Balance Bal;
    }

    public interface IBot
    {
        string Name { get; }
        BotAction Decide(BotView v);
    }

    /// <summary>共通の補助。</summary>
    internal static class BotHelp
    {
        /// <summary>自分の空きスロットを埋められるラインの位置。無ければ -1。</summary>
        public static int FindFitting(BotView v, bool preferMaker, Manufacturer want)
        {
            int fallback = -1;
            for (int i = 0; i < v.Line.Size; i++)
            {
                MechaCard c = v.Line.Peek(i);
                if (v.Self.IsFilled(c.Slot)) { continue; }
                if (preferMaker && c.Maker == want) { return i; }
                if (fallback < 0) { fallback = i; }
            }
            return preferMaker ? -1 : fallback;
        }

        public static int FindAnyFitting(BotView v)
        {
            return FindFitting(v, false, Manufacturer.Red);
        }

        /// <summary>装着済みで最も多いメーカー。役を寄せる目標になる。</summary>
        public static Manufacturer Majority(Workbench bench, int[] scratch)
        {
            bench.CountMakers(scratch);
            int best = 0;
            for (int i = 1; i < scratch.Length; i++)
            {
                if (scratch[i] > scratch[best]) { best = i; }
            }
            return (Manufacturer)best;
        }

        /// <summary>まだ上書きできるか。上限0は無制限。</summary>
        public static bool CanOverwriteMore(BotView v)
        {
            return v.Bal.MaxOverwritesPerBuild <= 0
                || v.OverwritesUsed < v.Bal.MaxOverwritesPerBuild;
        }

        /// <summary>役を良くする上書きの手。無ければ -1。</summary>
        public static int FindImprovingOverwrite(BotView v, Manufacturer want, int[] scratch)
        {
            for (int i = 0; i < v.Line.Size; i++)
            {
                MechaCard c = v.Line.Peek(i);
                if (c.Maker != want) { continue; }
                if (!v.Self.CanOverwrite(c.Slot)) { continue; }
                if (v.Self.MakerAt(c.Slot) == want) { continue; } // 既に同色なら無意味
                return i;
            }
            return -1;
        }

        /// <summary>
        /// 引き直す1枚を選ぶ。埋まっている部位のカードが最も要らない。
        /// パージ（4枚まとめ）は廃止したので、1枚ずつ回す。仕様書 9-5l。
        /// </summary>
        public static int PickDiscard(BotView v)
        {
            for (int i = 0; i < v.Line.Size; i++)
            {
                if (v.Self.IsFilled(v.Line.Peek(i).Slot)) { return i; }
            }
            return 0;
        }
    }

    /// <summary>
    /// 速攻ボット。役を完全に無視し、埋まる札を最速で投げて即出撃する。
    /// 仕様書 9-2 の基準の片方。
    /// </summary>
    public class RushBot : IBot
    {
        public string Name { get { return "速攻"; } }

        public BotAction Decide(BotView v)
        {
            if (v.Self.IsComplete) { return BotAction.Of(ActionKind.Launch, 0); }

            int i = BotHelp.FindAnyFitting(v);
            if (i >= 0) { return BotAction.Of(ActionKind.TakeToSelf, i); }

            return BotAction.Of(ActionKind.Purge, 0);
        }
    }

    /// <summary>
    /// 役狙いボット。時間を無視して役を上げにいく。
    /// 仕様書 9-2 の基準のもう片方。
    /// </summary>
    public class HandBot : IBot
    {
        private readonly int[] _scratch = new int[Counts.Manufacturers];
        private readonly Hand _launchThreshold;
        private readonly int _maxHoldMs;

        public string Name { get { return "役狙い"; } }

        public HandBot(Hand launchThreshold = Hand.FullHouse, int maxHoldMs = 8000)
        {
            _launchThreshold = launchThreshold;
            _maxHoldMs = maxHoldMs;
        }

        public BotAction Decide(BotView v)
        {
            Manufacturer want = BotHelp.Majority(v.Self, _scratch);

            if (v.Self.IsComplete)
            {
                Hand h = v.Self.EvaluateHand();
                if (h >= _launchThreshold || v.HeldMs >= _maxHoldMs
                    || !BotHelp.CanOverwriteMore(v))
                {
                    return BotAction.Of(ActionKind.Launch, 0);
                }

                int ow = BotHelp.FindImprovingOverwrite(v, want, _scratch);
                if (ow >= 0) { return BotAction.Of(ActionKind.Overwrite, ow); }

                // 欲しい色が流れていない。引き直して探す
                return BotAction.Of(ActionKind.Purge, 0);
            }

            // 未完成：狙った色で埋められるならそれを優先
            int pref = BotHelp.FindFitting(v, true, want);
            if (pref >= 0) { return BotAction.Of(ActionKind.TakeToSelf, pref); }


            // 色は合わないが埋まる札があるなら、進める
            int any = BotHelp.FindAnyFitting(v);
            if (any >= 0) { return BotAction.Of(ActionKind.TakeToSelf, any); }

            return BotAction.Of(ActionKind.Purge, 0);
        }
    }

    /// <summary>
    /// 指定した役に届くまで組み続け、届いたら出撃するボット。
    /// 「その役に到達するまでに何秒かかるか」を測るための計測用。
    /// 倍率は理論上の希少度ではなく、この実コストに比例させるべき。
    /// </summary>
    public class TargetBot : IBot
    {
        private readonly int[] _scratch = new int[Counts.Manufacturers];
        private readonly int[] _lineScratch = new int[Counts.Manufacturers];
        private readonly Hand _target;
        private readonly int _giveUpMs;
        private readonly int _patience;

        public string Name { get { return HandEvaluator.NameOf(_target) + "狙い"; } }
        public Hand Target { get { return _target; } }

        /// <param name="patience">
        /// 1機あたり、選り好みして引き直せる枚数。これを超えたら来た札で組む。
        ///
        /// これを入れないと、ボットは **1機あたり30回も引き直す**。
        /// 人間はそんなことをしないし、粘っている間に部位破壊で崩されて
        /// 93秒で1.7回しか出撃できない、という現実に無い状況が測れてしまう。
        /// </param>
        public TargetBot(Hand target, int giveUpMs = 30000, int patience = 4)
        {
            _target = target;
            _giveUpMs = giveUpMs;
            _patience = patience;
        }

        public BotAction Decide(BotView v)
        {
            bool wantPrism = (_target == Hand.Prism);
            v.Self.CountMakers(_scratch);

            // 選り好みの上限。使い切ったら、埋まる札を素直に取る。
            bool picky = v.DiscardsThisBuild < _patience;

            if (v.Self.IsComplete)
            {
                Hand h = v.Self.EvaluateHand();
                bool reached = wantPrism ? (h == Hand.Prism) : (h >= _target && h != Hand.Prism);
                if (reached || v.HeldMs >= _giveUpMs) { return BotAction.Of(ActionKind.Launch, 0); }

                // 上書きを使い切ったら、これ以上機体は直せない。撃つしかない。
                if (!BotHelp.CanOverwriteMore(v)) { return BotAction.Of(ActionKind.Launch, 0); }

                if (wantPrism)
                {
                    // 重複している色のスロットを、未使用の色で置き換える
                    for (int i = 0; i < v.Line.Size; i++)
                    {
                        MechaCard c = v.Line.Peek(i);
                        if (_scratch[(int)c.Maker] > 0) { continue; }
                        if (!v.Self.CanOverwrite(c.Slot)) { continue; }
                        if (_scratch[(int)v.Self.MakerAt(c.Slot)] <= 1) { continue; }
                        return BotAction.Of(ActionKind.Overwrite, i);
                    }
                }
                else
                {
                    Manufacturer want = ChooseWant(v);
                    int ow = BotHelp.FindImprovingOverwrite(v, want, _scratch);
                    if (ow >= 0) { return BotAction.Of(ActionKind.Overwrite, ow); }
                }
                return BotAction.Of(ActionKind.Purge, 0);
            }

            if (wantPrism)
            {
                // まだ使っていない色で空きを埋める
                for (int i = 0; i < v.Line.Size; i++)
                {
                    MechaCard c = v.Line.Peek(i);
                    if (v.Self.IsFilled(c.Slot)) { continue; }
                    if (picky && _scratch[(int)c.Maker] > 0) { continue; }
                    return BotAction.Of(ActionKind.TakeToSelf, i);
                }
            }
            else
            {
                Manufacturer want = ChooseWant(v);

                // 目標に必要な同色の枚数。ここに届いたら、あとは色を選ばず埋める。
                // これを入れないと、どの目標でも主要色だけを取り続けて
                // 結局ピュアカラーになるまで組んでしまう。
                int need = NeededSameColor(_target);
                bool stillNeedColor = picky && _scratch[(int)want] < need;

                if (stillNeedColor)
                {
                    int pref = BotHelp.FindFitting(v, true, want);
                    if (pref >= 0) { return BotAction.Of(ActionKind.TakeToSelf, pref); }
                }
                else
                {
                    int any = BotHelp.FindAnyFitting(v);
                    if (any >= 0) { return BotAction.Of(ActionKind.TakeToSelf, any); }
                }
            }

            return BotAction.Of(ActionKind.Purge, 0);
        }

        /// <summary>
        /// 寄せる色を決める。
        ///
        /// 以前は BotHelp.Majority() をそのまま使っていたが、作業台が空のときは
        /// 全部0になるので **必ず先頭の色（レッド）を返していた**。
        /// 山札は1色5枚（5部位×1枚）しか無いため、両者が同時にレッドだけを追うと
        /// 5枚を分け合って誰も揃わなくなる。
        /// 「フルハウス狙い vs ピュアカラー狙いが100%時間切れ」の正体はこれで、
        /// ゲームの膠着ではなく計測器の欠陥だった（上書き0回・パージ219回がその証拠）。
        ///
        /// 空のときは、実際に共有ラインへ流れている色から選ぶ。
        /// 人間も「場に来ている色」に寄せるので、こちらのほうが実戦に近い。
        /// </summary>
        private Manufacturer ChooseWant(BotView v)
        {
            v.Self.CountMakers(_scratch);

            int best = 0;
            for (int i = 1; i < _scratch.Length; i++)
            {
                if (_scratch[i] > _scratch[best]) { best = i; }
            }
            if (_scratch[best] > 0) { return (Manufacturer)best; }

            // 作業台が空：ラインに多く流れている色を選ぶ
            for (int i = 0; i < _lineScratch.Length; i++) { _lineScratch[i] = 0; }
            for (int i = 0; i < v.Line.Size; i++)
            {
                _lineScratch[(int)v.Line.Peek(i).Maker]++;
            }
            int pick = 0;
            for (int i = 1; i < _lineScratch.Length; i++)
            {
                if (_lineScratch[i] > _lineScratch[pick]) { pick = i; }
            }
            return (Manufacturer)pick;
        }

        private static int NeededSameColor(Hand target)
        {
            switch (target)
            {
                case Hand.OnePair:      return 2;
                case Hand.TwoPair:      return 2;
                case Hand.ThreeOfAKind: return 3;
                case Hand.FullHouse:    return 3;
                case Hand.FourOfAKind:  return 4;
                case Hand.PureColor:    return 5;
                default:                return 2;
            }
        }
    }

    /// <summary>
    /// プリズム狙いボット。5色を1枚ずつ集めて「完全に散らす」ことを目指す。
    /// 仕様書 4-1 の「揃えるか、完全に散らすか。両極が強い」が
    /// 戦術として本当に成立するのかを確かめるために置く。
    /// </summary>
    public class PrismBot : IBot
    {
        private readonly int[] _scratch = new int[Counts.Manufacturers];
        private readonly int _maxHoldMs;

        public string Name { get { return "プリズム狙い"; } }

        public PrismBot(int maxHoldMs = 8000)
        {
            _maxHoldMs = maxHoldMs;
        }

        public BotAction Decide(BotView v)
        {
            v.Self.CountMakers(_scratch);

            if (v.Self.IsComplete)
            {
                Hand h = v.Self.EvaluateHand();
                // プリズムに届いた、待ちすぎた、または上書きを使い切ったら出す
                if (h == Hand.Prism || v.HeldMs >= _maxHoldMs
                    || !BotHelp.CanOverwriteMore(v))
                {
                    return BotAction.Of(ActionKind.Launch, 0);
                }

                // 重複している色のスロットを、未使用の色で置き換える
                for (int i = 0; i < v.Line.Size; i++)
                {
                    MechaCard c = v.Line.Peek(i);
                    if (_scratch[(int)c.Maker] > 0) { continue; }        // 未使用の色だけ
                    if (!v.Self.CanOverwrite(c.Slot)) { continue; }
                    if (_scratch[(int)v.Self.MakerAt(c.Slot)] <= 1) { continue; } // 重複を潰す
                    return BotAction.Of(ActionKind.Overwrite, i);
                }
                return BotAction.Of(ActionKind.Purge, 0);
            }

            // 未完成：まだ使っていない色で空きスロットを埋める
            for (int i = 0; i < v.Line.Size; i++)
            {
                MechaCard c = v.Line.Peek(i);
                if (v.Self.IsFilled(c.Slot)) { continue; }
                if (_scratch[(int)c.Maker] > 0) { continue; }
                return BotAction.Of(ActionKind.TakeToSelf, i);
            }


            return BotAction.Of(ActionKind.Purge, 0);
        }
    }

    /// <summary>
    /// ガード多用ボット。亀化するかを測るために置く。仕様書 6-2d。
    /// 相手の機体が完成していたら守りに入る。
    /// </summary>
    public class GuardBot : IBot
    {
        private readonly int[] _scratch = new int[Counts.Manufacturers];
        private readonly int _guardHoldMs;

        public string Name { get { return "ガード多用"; } }

        public GuardBot(int guardHoldMs = 1200)
        {
            _guardHoldMs = guardHoldMs;
        }

        public BotAction Decide(BotView v)
        {
            // 相手が完成していたら、まず守る。
            // ただし完成必須の設定なら、自分の機体が無いと受けられない。
            bool canGuard = !v.Bal.GuardRequiresComplete || v.Self.IsComplete;
            if (v.Opponent.IsComplete && canGuard)
            {
                return BotAction.GuardFor(_guardHoldMs);
            }

            if (v.Self.IsComplete) { return BotAction.Of(ActionKind.Launch, 0); }

            int i = BotHelp.FindAnyFitting(v);
            if (i >= 0) { return BotAction.Of(ActionKind.TakeToSelf, i); }


            return BotAction.Of(ActionKind.Purge, 0);
        }
    }

    /// <summary>
    /// 「塗り替え」ボット。実機で見つかった打ち方をそのまま写したもの。仕様書 9-5p。
    ///
    ///   「変えられるパーツカードを残し、上書き用のパーツカードを連打することで
    ///     ピュアカラーが出しやすくなる」
    ///
    /// 手順は2段階。
    ///   1. 色を一切問わず、埋まる札を投げて **とにかく5枚そろえる**
    ///   2. そこから、狙った色の札を **引き直しで探しては上書きする**
    ///
    /// 各部位は1回だけ上書きできるので、最大5回＝機体まるごと塗り替えられる。
    /// 速攻の「速さ」と役狙いの「純度」を、順番にやることで両取りしようとする打ち方。
    ///
    /// 待つのではなく **引き直しを回す** ので、9-6e で測った「粘り」とは別の軸。
    /// </summary>
    public class RepaintBot : IBot
    {
        private readonly int[] _scratch = new int[Counts.Manufacturers];
        private readonly int _giveUpMs;
        private readonly bool _onlyOneAway;

        public string Name { get { return _onlyOneAway ? "あと1色だけ" : "塗り替え"; } }

        /// <param name="giveUpMs">完成してからこれだけ経ったら、塗り替え途中でも撃つ。</param>
        /// <param name="onlyOneAway">
        /// true なら **フォーカード（あと1枚でピュアカラー）のときだけ**塗り替えを試みる。
        /// 実機の証言はこちら ——「常に狙えるものでもない。あと1色となった時にやれるってだけ」。
        /// 上書きは1回で済むので、最初から全部塗り替える版よりずっと安い。
        /// </param>
        public RepaintBot(int giveUpMs = 12000, bool onlyOneAway = false)
        {
            _giveUpMs = giveUpMs;
            _onlyOneAway = onlyOneAway;
        }

        public BotAction Decide(BotView v)
        {
            // ---- 第1段階：色を問わず、とにかく埋める ----
            if (!v.Self.IsComplete)
            {
                int any = BotHelp.FindAnyFitting(v);
                if (any >= 0) { return BotAction.Of(ActionKind.TakeToSelf, any); }
                return BotAction.Of(ActionKind.Purge, 0);
            }

            // ---- 第2段階：多数派の色へ塗り替える ----
            Manufacturer want = BotHelp.Majority(v.Self, _scratch);

            // 「あと1色」だけを狙う打ち方なら、フォーカード以外は即撃つ
            if (_onlyOneAway && v.Self.EvaluateHand() != Hand.FourOfAKind)
            {
                return BotAction.Of(ActionKind.Launch, 0);
            }

            // もう塗り替えられる部位が無いか、粘りすぎたら撃つ
            bool anyLeft = false;
            for (int s = 0; s < Counts.Slots; s++)
            {
                PartSlot slot = (PartSlot)s;
                if (v.Self.CanOverwrite(slot) && v.Self.MakerAt(slot) != want) { anyLeft = true; break; }
            }
            if (!anyLeft || v.HeldMs >= _giveUpMs || !BotHelp.CanOverwriteMore(v))
            {
                return BotAction.Of(ActionKind.Launch, 0);
            }

            // 狙った色の札が場にあれば上書き。無ければ引き直して探す。
            int ow = BotHelp.FindImprovingOverwrite(v, want, _scratch);
            if (ow >= 0) { return BotAction.Of(ActionKind.Overwrite, ow); }

            return BotAction.Of(ActionKind.Purge, 0);
        }

        /// <summary>
        /// 塗り替えに使えない札から捨てる。
        /// 「狙った色で、まだ上書きできる部位」の札は残す ＝ 実機で言う「変えられるパーツカードを残す」。
        /// </summary>
        private static int PickForRepaint(BotView v, Manufacturer want)
        {
            for (int i = 0; i < v.Line.Size; i++)
            {
                MechaCard c = v.Line.Peek(i);
                bool useful = c.Maker == want
                              && v.Self.CanOverwrite(c.Slot)
                              && v.Self.MakerAt(c.Slot) != want;
                if (!useful) { return i; }
            }
            return 0;
        }
    }
}
