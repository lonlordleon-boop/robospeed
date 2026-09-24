using System;

namespace RoboSpeed.Core
{
    /// <summary>
    /// メーカー（＝色）。5社。仕様書 3-1。
    /// 社名は未定のため、当面は色で識別する。
    /// </summary>
    public enum Manufacturer
    {
        Red = 0,
        Blue = 1,
        Yellow = 2,
        Green = 3,
        White = 4,
    }

    /// <summary>
    /// 機体のスロット。5つ。仕様書 3-1。
    /// 両腕・両脚はそれぞれ1スロット（左右は分けない）。
    /// </summary>
    public enum PartSlot
    {
        Head = 0,
        Torso = 1,
        Waist = 2,
        Arms = 3,
        Legs = 4,
    }

    /// <summary>
    /// 役。7段階。仕様書 4-1。
    /// 値が大きいほど強い。ピュアカラーとプリズムが両極。
    /// </summary>
    public enum Hand
    {
        /// <summary>2-1-1-1。最も出やすい（38.40%）。基準。</summary>
        OnePair = 0,
        /// <summary>2-2-1（28.80%）。</summary>
        TwoPair = 1,
        /// <summary>3-1-1（19.20%）。</summary>
        ThreeOfAKind = 2,
        /// <summary>3-2（6.40%）。</summary>
        FullHouse = 3,
        /// <summary>1-1-1-1-1（3.84%）。全色1枚ずつ。専用形態に変身。</summary>
        Prism = 4,
        /// <summary>4-1（3.20%）。</summary>
        FourOfAKind = 5,
        /// <summary>5（0.16%）。全部同色。専用形態に変身。</summary>
        PureColor = 6,
    }

    /// <summary>
    /// メカカード。メーカー × スロットの組み合わせ。
    /// 山札は 5メーカー × 5スロット = 25枚。仕様書 3-1。
    /// </summary>
    public struct MechaCard : IEquatable<MechaCard>
    {
        public readonly Manufacturer Maker;
        public readonly PartSlot Slot;

        public MechaCard(Manufacturer maker, PartSlot slot)
        {
            Maker = maker;
            Slot = slot;
        }

        public bool Equals(MechaCard other)
        {
            return Maker == other.Maker && Slot == other.Slot;
        }

        public override bool Equals(object obj)
        {
            return obj is MechaCard && Equals((MechaCard)obj);
        }

        public override int GetHashCode()
        {
            return ((int)Maker * 8) + (int)Slot;
        }

        public override string ToString()
        {
            return Maker + "/" + Slot;
        }
    }

    /// <summary>列挙の要素数をひとまとめに。マジックナンバーを散らさないため。</summary>
    public static class Counts
    {
        public const int Manufacturers = 5;
        public const int Slots = 5;
        public const int DeckSize = Manufacturers * Slots; // 25
    }
}
