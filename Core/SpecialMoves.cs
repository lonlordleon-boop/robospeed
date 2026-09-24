using System;

namespace RoboSpeed.Core
{
    /// <summary>
    /// 必殺技。仕様書 6-2c。
    /// 各メーカーが1つずつ持ち、機体に使われているメーカーの技が選択肢に並ぶ。
    /// 名称は機能名にとどめている。既存作品の固有技名は使わない（命名規則）。
    /// </summary>
    public struct SpecialMove
    {
        public readonly Manufacturer Owner;
        public readonly string Name;
        /// <summary>基礎威力。役倍率が乗る前の値。</summary>
        public readonly double BaseDamage;
        /// <summary>装填時間の補正（ミリ秒）。負なら短くなる＝手数型。</summary>
        public readonly int ReloadDeltaMs;
        /// <summary>相手の作業台からパーツを1つ吹き飛ばす。妨害兼用。</summary>
        public readonly bool StripsPart;
        /// <summary>ガードを貫通する割合。0.5 なら削り軽減が半分しか効かない。</summary>
        public readonly double GuardPierce;

        public SpecialMove(Manufacturer owner, string name, double baseDamage,
                           int reloadDeltaMs, bool stripsPart, double guardPierce)
        {
            Owner = owner;
            Name = name;
            BaseDamage = baseDamage;
            ReloadDeltaMs = reloadDeltaMs;
            StripsPart = stripsPart;
            GuardPierce = guardPierce;
        }
    }

    public static class SpecialMoves
    {
        /// <summary>
        /// メーカーごとに1つ。仕様書 6-2c の「効果の方向」に対応。
        ///
        /// ---- 基礎威力の幅を 1.63倍 → 1.21倍 に狭めた理由（仕様書 9-5m）----
        ///
        /// 旧値は 80〜130 と開いていた。役1段の差は ×1.33 しかないので、
        /// **色の差が役の差を食っていた。** 実機ログ（22出撃）にそのまま出た。
        ///
        ///   フルハウス（赤・130）337  ＞  フォーカード（緑・100）325
        ///   ツーペア  （赤・130）173  ＞  スリーカード（黄・ 90）160
        ///   フルハウス（赤）337 対 フルハウス（青）207 ＝ 同じ役で1.63倍
        ///
        /// 役を1段上げても色が悪ければ弱くなる状態では「役を狙う」判断が成立しない。
        /// 設計上は装填時間（赤+400 / 青-400）で釣り合うはずだったが、
        /// **組み立てが実測10.7秒**なので ±400ms は1周期の3%にしかならない。
        /// 撃つと機体が消えるので「連射で取り返す」状況が存在しなかった。
        ///
        /// 基準：**色による威力差は、役1段（×1.33）より小さくすること。**
        /// 色の個性は威力ではなく **装填・部位破壊・貫通** の側に置く。
        /// </summary>
        public static readonly SpecialMove[] ByMaker =
        {
            // 斬撃系：単発の威力はいちばん高いが装填が長い
            new SpecialMove(Manufacturer.Red,    "斬撃",  115, +400, false, 0.0),
            // 砲撃系：威力は控えめだが装填が短い＝手数型
            new SpecialMove(Manufacturer.Blue,   "砲撃",   95, -400, false, 0.0),
            // 拡散弾系：相手の作業台からパーツを1つ吹き飛ばす
            new SpecialMove(Manufacturer.Yellow, "拡散弾",  98,    0,  true, 0.0),
            // 打撃系：ガードを半分貫通する
            new SpecialMove(Manufacturer.Green,  "打撃",  100,    0, false, 0.5),
            // 貫通系：中庸。装填やや短め
            new SpecialMove(Manufacturer.White,  "貫通",  105, -150, false, 0.25),
        };

        /// <summary>
        /// プリズム（5社が1枚ずつ）専用の攻撃。
        ///
        /// 必殺技の選択を廃止した（6-2c）ことで、「選択肢が5つある」という
        /// プリズムの存在理由が消えた。代わりに専用の連携攻撃を持たせる。
        /// 全社の機構が乗るので、部位破壊と貫通を併せ持つ。
        /// </summary>
        /// 威力は **色の幅の中での位置** を保つ。
        /// 旧: 120（幅 80〜130 の8割の位置） / 新: 111（幅 95〜115 の8割の位置）。
        /// 幅を狭めたのに120のままだと、プリズムだけが全色より強くなってしまう。
        public static readonly SpecialMove Prism =
            new SpecialMove((Manufacturer)(-1), "全機連携", 111, -200, true, 0.25);

        public static SpecialMove Of(Manufacturer maker)
        {
            return ByMaker[(int)maker];
        }

        /// <summary>
        /// 機体の組み合わせから技を決める。**プレイヤーには選ばせない。**
        ///
        /// 選択画面を挟むと、そのたびに両者が止まってテンポが落ちる
        /// （実機：「テンポが悪くなるから、必殺技を選ぶのをやめて」）。
        /// 組み合わせで決まるなら、**組む段階での選択がそのまま技の選択**になる。
        ///
        ///   ・最も多く使われているメーカーの技
        ///   ・同数で並んだら、胸（コア）のメーカーを優先
        ///   ・5社が1枚ずつ（プリズム）は専用の連携攻撃
        ///
        /// 同数のときに胸を見るのが効いていて、
        /// **同じ5枚でも「どの色を胸に置くか」で技が変わる。**
        /// </summary>
        public static SpecialMove MoveOf(Workbench bench)
        {
            int[] count = new int[Counts.Manufacturers];
            bench.CountMakers(count);

            int top = 0;
            for (int i = 1; i < count.Length; i++)
            {
                if (count[i] > count[top]) { top = i; }
            }
            if (count[top] == 1) { return Prism; }      // 全部1枚ずつ

            // 同数で並んだメーカーのうち、胸のメーカーがいればそれを使う
            Manufacturer core = bench.MakerAt(PartSlot.Torso);
            if (count[(int)core] == count[top]) { return ByMaker[(int)core]; }

            return ByMaker[top];
        }

        /// <summary>
        /// 主色 ＝ 最も多く使われている色。同数なら胸の色。
        ///
        /// **プリズム（全部1枚ずつ）でも -1 を返さない。** 全色が同数で並ぶので、
        /// 胸の色が主色になる。これにより図鑑でプリズムにも5つの型ができる（9-5n／5-2b）。
        /// </summary>
        public static int PrimaryMakerOf(Workbench bench)
        {
            int[] c = new int[Counts.Manufacturers];
            bench.CountMakers(c);

            int top = 0;
            for (int i = 1; i < c.Length; i++) { if (c[i] > c[top]) { top = i; } }

            int core = (int)bench.MakerAt(PartSlot.Torso);
            if (c[core] == c[top]) { return core; }
            return top;
        }

        /// <summary>
        /// 順位 rank の色（1 ＝ 副色、2 ＝ 第三色）。残っていなければ -1。
        ///
        /// 主色から順に「使われている枚数が多い色」を取り出していく。
        /// **同数で並んだら、部位の順（頭・胸・腰・腕・脚）で先に現れた色を採る。**
        ///
        /// v1.8 までは同数のとき -1（＝無し）にしていたが、それだと
        /// ワンペア(2-1-1-1)とスリーカード(3-1-1)で副色が立たず、
        /// 図鑑のエントリが 80 にしかならなかった。部位順で解くと 125、
        /// 第三色まで使うと **285**。3,125通りの全数走査で確認済み（5-2b）。
        /// </summary>
        public static int NthMakerOf(Workbench bench, int rank)
        {
            int[] c = new int[Counts.Manufacturers];
            bench.CountMakers(c);

            bool[] used = new bool[Counts.Manufacturers];
            used[PrimaryMakerOf(bench)] = true;

            int pick = -1;
            for (int r = 1; r <= rank; r++)
            {
                int top = -1;
                for (int i = 0; i < c.Length; i++)
                {
                    if (used[i]) { continue; }
                    if (top < 0 || c[i] > c[top]) { top = i; }
                }
                if (top < 0 || c[top] == 0) { return -1; }

                // 同数で並んだら部位の順で先に出た色
                pick = top;
                int tied = 0;
                for (int i = 0; i < c.Length; i++) { if (!used[i] && c[i] == c[top]) { tied++; } }
                if (tied > 1)
                {
                    for (int s = 0; s < Counts.Slots; s++)
                    {
                        int m = (int)bench.MakerAt((PartSlot)s);
                        if (!used[m] && c[m] == c[top]) { pick = m; break; }
                    }
                }
                used[pick] = true;
            }
            return pick;
        }

        /// <summary>第三色。背中の装備を決める。無ければ -1。</summary>
        public static int ThirdMakerOf(Workbench bench)
        {
            return NthMakerOf(bench, 2);
        }

        /// <summary>
        /// 副色 ＝ 主色を除いて最も多く使われている色。手に持つ武器を決める。
        ///
        /// **今まで捨てられていた情報。** 3-2 のフルハウスなら、技を決めるのは3枚側だけで、
        /// 「どの色でペアを組んだか」はどこにも効いていなかった。
        ///
        /// ピュアカラーは他の色が無いので -1（＝素手）。
        /// **これは仕様どおり。** 「純度が上がるほど機体は簡潔になる」（5-2b）。
        ///
        /// 注意：副色の**数値効果**（`Balance.SubColorScale`、既定 0 で無効）を復活させる場合、
        /// ピュアカラーだけ恩恵が無くなり実測で 43.3% → 27.0% まで落ちた。
        /// そのときは呼び出し側で「-1 なら主色で代用する」処理を入れること。
        /// **この関数自体は事実を返す。**
        /// </summary>
        public static int SubMakerOf(Workbench bench)
        {
            return NthMakerOf(bench, 1);
        }

        /// <summary>
        /// 機体に使われているメーカーの技を選択肢として集める。
        /// 選択肢の数はそのまま「使ったメーカーの数」になる。
        /// ピュアカラー=1、プリズム=5。
        /// </summary>
        public static int CollectOptions(Workbench bench, SpecialMove[] into)
        {
            bool[] seen = new bool[Counts.Manufacturers];
            int n = 0;
            for (int i = 0; i < Counts.Slots; i++)
            {
                PartSlot s = (PartSlot)i;
                if (!bench.IsFilled(s)) { continue; }
                int m = (int)bench.MakerAt(s);
                if (seen[m]) { continue; }
                seen[m] = true;
                into[n++] = ByMaker[m];
            }
            return n;
        }
    }
}
