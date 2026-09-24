using System;
using System.Collections.Generic;

namespace RoboSpeed.Core
{
    /// <summary>
    /// 山札と共有ライン。仕様書 3-2／3-3／3-3b。
    /// 山札25枚は1試合で必ず枯渇するので、捨て札をシャッフルして循環させる。
    /// </summary>
    public class SupplyLine
    {
        private readonly List<MechaCard> _draw = new List<MechaCard>();
        private readonly List<MechaCard> _discard = new List<MechaCard>();
        private readonly MechaCard[] _line;
        private readonly Random _rng;

        /// <summary>循環した回数。山札が足りているかの目安になる。</summary>
        public int RecycleCount { get; private set; }

        public int Size { get { return _line.Length; } }

        /// <summary>
        /// 無限供給。山札という概念を持たず、毎回その場で1枚を等確率で湧かせる。
        /// 決着は本拠地ゲージのみなので、供給が尽きて試合が止まることは無い。
        /// 捨て札の循環と違い「さっき捨てた色がすぐ戻ってくる」相関が消える。
        /// </summary>
        public bool Infinite { get; set; }

        public SupplyLine(Random rng, int lineSize, int copies)
        {
            _rng = rng;
            _line = new MechaCard[lineSize];
            if (copies < 1) { copies = 1; }

            // 5メーカー × 5スロット × 枚数
            for (int c = 0; c < copies; c++)
            {
                for (int m = 0; m < Counts.Manufacturers; m++)
                {
                    for (int s = 0; s < Counts.Slots; s++)
                    {
                        _draw.Add(new MechaCard((Manufacturer)m, (PartSlot)s));
                    }
                }
            }
            Shuffle(_draw);

            for (int i = 0; i < _line.Length; i++)
            {
                _line[i] = DrawOne();
            }
        }

        public MechaCard Peek(int index)
        {
            return _line[index];
        }

        /// <summary>
        /// 1枚取る。取られた場所は即座に補充される。
        /// 先にフリックした側が取る（競合の解決は呼び出し側の時刻順で行う）。
        /// </summary>
        public MechaCard Take(int index)
        {
            MechaCard card = _line[index];
            _line[index] = DrawOne();
            return card;
        }

        /// <summary>使える札を1枚引く。仕様書 9-5r。isDead が null なら従来どおり。</summary>
        public MechaCard Take(int index, Func<MechaCard, bool> isDead)
        {
            MechaCard card = _line[index];
            _line[index] = DrawUsable(isDead);
            return card;
        }

        /// <summary>パージ。ライン全部を捨てて引き直す。仕様書 3-3。</summary>
        public void Purge()
        {
            Purge(null);
        }

        /// <summary>パージ（使えない札は配らない）。仕様書 3-3／9-5r。</summary>
        public void Purge(Func<MechaCard, bool> isDead)
        {
            for (int i = 0; i < _line.Length; i++)
            {
                _discard.Add(_line[i]);
                _line[i] = DrawUsable(isDead);
            }
        }

        /// <summary>
        /// 作業台が変わって使えなくなった札を、配り直す。仕様書 9-5r。
        /// 上書きでも作業台は変わるので、毎ティック呼ぶ。
        /// </summary>
        public void Refresh(Func<MechaCard, bool> isDead)
        {
            if (isDead == null) { return; }
            for (int i = 0; i < _line.Length; i++)
            {
                if (!isDead(_line[i])) { continue; }
                _discard.Add(_line[i]);
                _line[i] = DrawUsable(isDead);
            }
        }

        /// <summary>
        /// **山をなぞって、使える札を1枚抜く。** 仕様書 9-5r。
        ///
        /// 「引く → 使えなければ捨て札へ → もう一度引く」を回数制限つきで回すと、
        /// 捨てた札が循環ですぐ山へ戻り、**同じ札を何度も引き直して打ち切られる。**
        /// 山は最初から混ぜてあるので、上から順に見て最初の1枚を取れば偏らない。
        /// 使えない札は山に残す（作業台が変われば、また使えるようになる）。
        /// </summary>
        private MechaCard DrawUsable(Func<MechaCard, bool> isDead)
        {
            if (isDead == null || Infinite) { return DrawOne(); }

            for (int pass = 0; pass < 2; pass++)
            {
                for (int i = _draw.Count - 1; i >= 0; i--)
                {
                    if (isDead(_draw[i])) { continue; }
                    MechaCard c = _draw[i];
                    _draw.RemoveAt(i);
                    return c;
                }
                if (_discard.Count == 0) { break; }
                _draw.AddRange(_discard);
                _discard.Clear();
                Shuffle(_draw);
                RecycleCount++;
            }
            // 山にも捨て札にも1枚も無い。**止まらないための保険。**
            // この状態（5部位すべて埋まり、上書きも使い切った）は強制出撃で即座に解消される。
            return DrawOne();
        }

        /// <summary>役目を終えたカードを捨て札へ。全損した機体のパーツなど。</summary>
        public void Discard(MechaCard card)
        {
            _discard.Add(card);
        }

        private MechaCard DrawOne()
        {
            if (Infinite)
            {
                return new MechaCard(
                    (Manufacturer)_rng.Next(Counts.Manufacturers),
                    (PartSlot)_rng.Next(Counts.Slots));
            }

            if (_draw.Count == 0)
            {
                // 捨て札をシャッフルして山札に戻す。仕様書 3-3b。
                if (_discard.Count == 0)
                {
                    // 理論上ここには来ない（全カードが盤面に出ている状態）
                    // 供給が途切れるとゲームが止まるので、安全のため作り直す
                    for (int m = 0; m < Counts.Manufacturers; m++)
                    {
                        for (int s = 0; s < Counts.Slots; s++)
                        {
                            _draw.Add(new MechaCard((Manufacturer)m, (PartSlot)s));
                        }
                    }
                }
                else
                {
                    _draw.AddRange(_discard);
                    _discard.Clear();
                }
                Shuffle(_draw);
                RecycleCount++;
            }

            int last = _draw.Count - 1;
            MechaCard card = _draw[last];
            _draw.RemoveAt(last);
            return card;
        }

        private void Shuffle(List<MechaCard> list)
        {
            for (int i = list.Count - 1; i > 0; i--)
            {
                int j = _rng.Next(i + 1);
                MechaCard t = list[i];
                list[i] = list[j];
                list[j] = t;
            }
        }
    }
}
