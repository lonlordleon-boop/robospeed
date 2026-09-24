using System;

namespace RoboSpeed.Core
{
    /// <summary>攻撃1回の結果。集計用。</summary>
    public struct AttackResult
    {
        public Hand AttackerHand;
        public SpecialMove Move;
        public bool WasGuarded;
        public double Damage;
        public int ReloadMs;
        public int EffectMs;
    }

    /// <summary>
    /// ダメージ計算。仕様書 6-2b。
    ///
    ///   通常   = 必殺技の基礎値 × 攻撃側の役倍率 × 背水補正
    ///   ガード = 通常 × ガード係数 ÷ 守備側の役倍率
    ///
    /// 1つの倍率表が攻撃と防御の両方を兼ねる。
    /// </summary>
    public static class CombatResolver
    {
        public static AttackResult Resolve(
            Balance bal,
            Hand attackerHand,
            SpecialMove move,
            double attackerHpRatio,
            bool defenderGuarding,
            bool defenderComplete,
            Hand defenderHand)
        {
            AttackResult r = new AttackResult();
            r.AttackerHand = attackerHand;
            r.Move = move;
            r.WasGuarded = defenderGuarding;

            double dmg = move.BaseDamage * bal.MultiplierOfScaled(attackerHand);

            // 背水。追い込まれた側の攻撃力が上がる。仕様書 6-5。
            if (attackerHpRatio <= bal.DesperationThreshold)
            {
                dmg *= bal.DesperationMultiplier;
            }

            if (defenderGuarding)
            {
                // 未完成の機体で受けると守備倍率は ×1.0。仕様書 6-2b。
                double defMul = defenderComplete ? bal.MultiplierOfScaled(defenderHand) : 1.0;

                double reduced = dmg * bal.GuardCoefficient / defMul;

                // 貫通系はガードの軽減を部分的に無効化する
                if (move.GuardPierce > 0.0)
                {
                    reduced = reduced + (dmg - reduced) * move.GuardPierce;
                }
                dmg = reduced;
            }

            r.Damage = dmg;
            r.EffectMs = bal.EffectMsOf(attackerHand);

            int reload = bal.ReloadMsOf(attackerHand) + move.ReloadDeltaMs;
            r.ReloadMs = reload < 100 ? 100 : reload;

            return r;
        }
    }
}
