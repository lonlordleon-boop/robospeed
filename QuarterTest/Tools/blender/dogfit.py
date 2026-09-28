# -*- coding: utf-8 -*-
"""犬のメッシュを測って、Rigify のメタリグを置く座標（BONES）を出す。

   dog_rig.py の BONES は仮モデルの寸法を手打ちしてあった。
   メッシュを入れ替えるたびに測り直すのは手間なので、形から自動で出す。

   やっていること：
   1. glb を読み、向きと大きさをそろえる（前は -Y、上は +Z、足が z=0、高さを HEIGHT に）
   2. 前後の位置ごとに「体の上端・下端」を測り、その線に沿って背骨を置く
      （犬種によって背中の傾きが違う。柴の子犬は胴の中ほどが高く、腰が大きく下がっていた）
   3. 脚・頭・尻尾の位置を測って BONES を組み立て、JSON に書き出す

   実行: blender -b -P dogfit.py -- 入力.glb 出力.json [そろえたメッシュ.glb]
"""
import bpy, sys, os, json
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(a[0])
OUTJ = os.path.abspath(a[1])
OUTG = os.path.abspath(a[2]) if len(a) > 2 else None

HEIGHT = 0.788          # 仮モデルと同じ高さにそろえる（park12.html の見え方を変えないため）

LOG = []
def log(s):
    LOG.append(str(s)); print("[fit] " + str(s))

# ---------------------------------------------------------------- 読み込み
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=SRC)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not meshes:
    log("メッシュが無い"); sys.exit(1)
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
mesh = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = mesh.data
P = np.array([tuple(v.co) for v in me.vertices])
log("読み込み: 頂点 %d" % len(P))

# ---------------------------------------------------------------- 向きと大きさをそろえる
size = P.max(axis=0) - P.min(axis=0)
axis_w = int(np.argmin(size))                       # 左右（一番うすい向き）
rest = [i for i in range(3) if i != axis_w]
axis_up = rest[int(np.argmax([size[rest[0]], size[rest[1]]]))]
axis_fw = [i for i in rest if i != axis_up][0]
log("軸: 左右=%s 前後=%s 上=%s（元の大きさ %.3f, %.3f, %.3f）"
    % ("xyz"[axis_w], "xyz"[axis_fw], "xyz"[axis_up], size[0], size[1], size[2]))
Q = np.stack([P[:, axis_w], P[:, axis_fw], P[:, axis_up]], axis=1)

zmid = (Q[:, 2].min() + Q[:, 2].max()) / 2          # 上下：足は細いので下半分の頂点が少ない
if (Q[:, 2] > zmid).sum() < (Q[:, 2] < zmid).sum():
    Q[:, 2] *= -1
    log("上下をひっくり返した")

hi = Q[Q[:, 2] > Q[:, 2].min() + 0.75 * (Q[:, 2].max() - Q[:, 2].min())]
ymid = (Q[:, 1].min() + Q[:, 1].max()) / 2          # 前後：高い所が張り出している側が頭
if abs(hi[:, 1].max() - ymid) > abs(hi[:, 1].min() - ymid):
    Q[:, 1] *= -1
    log("前後をひっくり返した（前を -Y にそろえる）")

scale = HEIGHT / (Q[:, 2].max() - Q[:, 2].min())
Q *= scale
Q[:, 0] -= (Q[:, 0].min() + Q[:, 0].max()) / 2
Q[:, 1] -= (Q[:, 1].min() + Q[:, 1].max()) / 2
Q[:, 2] -= Q[:, 2].min()
H = float(Q[:, 2].max())
log("そろえた後: 倍率 %.4f / 前後 %.3f〜%.3f / 幅 %.3f / 高さ %.3f"
    % (scale, Q[:, 1].min(), Q[:, 1].max(), Q[:, 0].max() - Q[:, 0].min(), H))

for i, v in enumerate(me.vertices):
    v.co = Vector((float(Q[i, 0]), float(Q[i, 1]), float(Q[i, 2])))
me.update()

# ---------------------------------------------------------------- 測る道具
def band(y0, half=0.045, xw=0.20):
    return Q[(np.abs(Q[:, 1] - y0) < half * H) & (np.abs(Q[:, 0]) < xw * H)]

def top_at(y0, **kw):
    b = band(y0, **kw)
    return float(np.percentile(b[:, 2], 98)) if len(b) > 8 else None

def bottom_at(y0, **kw):
    b = band(y0, **kw)
    return float(np.percentile(b[:, 2], 2)) if len(b) > 8 else None

# ---------------------------------------------------------------- 脚
legs = Q[Q[:, 2] < 0.22 * H]                        # 下から22%までを脚とみなす
ycut = (legs[:, 1].min() + legs[:, 1].max()) / 2
front, rear = legs[legs[:, 1] < ycut], legs[legs[:, 1] >= ycut]

def leg_xy(g):
    side = g[g[:, 0] > 0]                           # 片側（左）だけ見る
    if len(side) < 10:
        side = g
    return float(np.median(np.abs(side[:, 0]))), float(np.median(g[:, 1]))

FRONT_X, FRONT_Y = leg_xy(front)
REAR_X, REAR_Y = leg_xy(rear)
FOOT_Z = 0.035 * H                                  # 足首の下、つま先のあたり
MID_Y = (FRONT_Y + REAR_Y) / 2                      # 前脚と後脚の間（ここに脚は無い）
BELLY_Z = bottom_at(MID_Y, half=0.05, xw=0.13)      # 胴の下（おなか）
BACK_Z = top_at(MID_Y, half=0.05, xw=0.16)          # 胴の上（背中）
log("前脚: x±%.3f y %.3f ／ 後脚: x±%.3f y %.3f" % (FRONT_X, FRONT_Y, REAR_X, REAR_Y))
log("胴の中ほど（y %.3f）: おなか %.3f ／ 背中 %.3f" % (MID_Y, BELLY_Z, BACK_Z))

# 脚の付け根は、見えている脚の上端ではなく「体の中」にある。
# ふさふさの犬ほど、肩と股関節は胴の輪郭よりだいぶ内側。
# ここを低く取ると脚が短くなり、走らせた時に胸が地面につくほどかがんでしまう。
# 走りの沈みは（脚の長さ）×0.21 くらいなので、おなかの高さから逆算して決めている
DEPTH = BACK_Z - BELLY_Z
SH_Z = BELLY_Z + 0.33 * DEPTH                       # 前脚の付け根（肩関節）
HP_Z = BELLY_Z + 0.38 * DEPTH                       # 後脚の付け根（股関節）
log("脚の付け根: 前 z %.3f ／ 後 z %.3f（おなかから上へ %.3f / %.3f）"
    % (SH_Z, HP_Z, SH_Z - BELLY_Z, HP_Z - BELLY_Z))

# ---------------------------------------------------------------- 背骨（背中の線に沿わせる）
CHEST_Y = FRONT_Y - 0.055 * H                       # 胸（前脚より少し前）
RUMP_Y = REAR_Y + 0.045 * H                         # 腰（後脚より少し後ろ）

def spine_pt(y0):
    """その前後位置での背骨の高さ。背中の少し内側に入れる（皮の上に置かない）"""
    t = top_at(y0, half=0.04, xw=0.16)
    b = bottom_at(y0, half=0.04, xw=0.13)
    if t is None:
        t, b = BACK_Z, BELLY_Z
    if b is None or b > t:
        b = BELLY_Z
    return (0.0, float(y0), float(t - 0.20 * (t - b)))

sp = [spine_pt(RUMP_Y + (CHEST_Y - RUMP_Y) * k / 4.0) for k in range(5)]   # 腰→胸の5点
log("背骨: " + " / ".join("y %.3f z %.3f" % (p[1], p[2]) for p in sp))

# ---------------------------------------------------------------- 頭・鼻・尻尾
# 頭の中心は「てっぺんの真下」で取る。
# 顔まわり（目・鼻・口）は頂点が密なので、頭ぜんたいの中央値を取ると鼻先へ引っぱられる
skull = Q[Q[:, 2] > 0.70 * H]
HEAD_Y = float(np.median(skull[:, 1]))
hb = Q[(np.abs(Q[:, 1] - HEAD_Y) < 0.07 * H) & (Q[:, 2] > 0.40 * H)]
HEAD_Z = float(np.median(hb[:, 2])) if len(hb) > 8 else 0.62 * H
NOSE_Y = float(Q[:, 1].min())
nose = Q[Q[:, 1] < NOSE_Y + 0.06 * H]
NOSE_Z = float(np.median(nose[:, 2]))
log("頭: y %.3f z %.3f ／ 鼻: y %.3f z %.3f" % (HEAD_Y, HEAD_Z, NOSE_Y, NOSE_Z))

TAIL_Y = float(Q[:, 1].max())
tcut = RUMP_Y + 0.45 * (TAIL_Y - RUMP_Y)
tail = Q[Q[:, 1] > tcut]
TAIL_MID_Z = float(np.median(tail[:, 2]))
tip = Q[Q[:, 1] > TAIL_Y - 0.06 * H]
TIP_Z = float(np.median(tip[:, 2]))
log("尻尾: 付け根 y %.3f ／ 中ほど z %.3f ／ 先 y %.3f z %.3f" % (tcut, TAIL_MID_Z, TAIL_Y, TIP_Z))

# ---------------------------------------------------------------- BONES を組み立てる
def lerp(a0, b0, t):
    return a0 + (b0 - a0) * t

B = {}
def bone(name, h, t):
    B[name] = [[float(h[0]), float(h[1]), float(h[2])], [float(t[0]), float(t[1]), float(t[2])]]

# 胴（後ろ→前）。spine.004 が根もとで、そこから尻尾と胴に分かれる
bone('spine.004', sp[0], sp[1])
bone('spine.005', sp[1], sp[2])
bone('spine.006', sp[2], sp[3])
bone('spine.007', sp[3], sp[4])
ch1 = (0, lerp(sp[4][1], HEAD_Y, 0.34), lerp(sp[4][2], HEAD_Z, 0.30))    # 胸（肩がここに付く）
ch2 = (0, lerp(sp[4][1], HEAD_Y, 0.68), lerp(sp[4][2], HEAD_Z, 0.68))    # 首
bone('spine.008', sp[4], ch1)
bone('spine.009', ch1, ch2)
bone('spine.010', ch2, (0, HEAD_Y, HEAD_Z))
bone('spine.011', (0, HEAD_Y, HEAD_Z), (0, NOSE_Y + 0.02 * H, NOSE_Z))   # 頭〜鼻づら
# 尻尾（4本で先まで）
t0 = sp[0]
t1 = (0, lerp(sp[0][1], tcut, 0.7), lerp(sp[0][2], TAIL_MID_Z, 0.7))
t2 = (0, tcut, TAIL_MID_Z)
t3 = (0, lerp(tcut, TAIL_Y, 0.55), lerp(TAIL_MID_Z, TIP_Z, 0.55))
t4 = (0, TAIL_Y - 0.01 * H, TIP_Z)
bone('spine.003', t0, t1)
bone('spine.002', t1, t2)
bone('spine.001', t2, t3)
bone('spine', t3, t4)
# 前脚（左。右は dog_rig.py が x を反転して作る）
fa = lerp(SH_Z, FOOT_Z, 0.74)                        # 足首
fk = lerp(SH_Z, FOOT_Z, 0.36)                        # ひじ
bone('shoulder.L', (0.45 * FRONT_X, CHEST_Y, SH_Z + 0.20 * DEPTH), (FRONT_X, FRONT_Y, SH_Z))
bone('front_thigh.L', (FRONT_X, FRONT_Y, SH_Z), (FRONT_X, FRONT_Y + 0.010 * H, fk))
bone('front_shin.L', (FRONT_X, FRONT_Y + 0.010 * H, fk), (FRONT_X, FRONT_Y - 0.022 * H, fa))
bone('front_foot.L', (FRONT_X, FRONT_Y - 0.022 * H, fa), (FRONT_X, FRONT_Y - 0.010 * H, FOOT_Z))
bone('front_toe.L', (FRONT_X, FRONT_Y - 0.010 * H, FOOT_Z), (FRONT_X, FRONT_Y - 0.075 * H, FOOT_Z * 0.4))
# 後脚（左）。ひざを前、飛節を後ろへ少し曲げる（まっすぐだと IK が向きを決められない）
ra = lerp(HP_Z, FOOT_Z, 0.72)
rk = lerp(HP_Z, FOOT_Z, 0.36)
bone('thigh.L', (REAR_X, REAR_Y, HP_Z), (REAR_X, REAR_Y - 0.008 * H, rk))
bone('shin.L', (REAR_X, REAR_Y - 0.008 * H, rk), (REAR_X, REAR_Y + 0.045 * H, ra))
bone('foot.L', (REAR_X, REAR_Y + 0.045 * H, ra), (REAR_X, REAR_Y + 0.030 * H, FOOT_Z))
bone('toe.L', (REAR_X, REAR_Y + 0.030 * H, FOOT_Z), (REAR_X, REAR_Y - 0.025 * H, FOOT_Z * 0.4))
# 骨盤と胸の飾り骨
bone('pelvis.L', (0, sp[0][1], sp[0][2] * 0.94), (0.8 * REAR_X, REAR_Y, sp[0][2] * 0.88))
bone('breast.L', (0.42 * FRONT_X, CHEST_Y, SH_Z + 0.35 * DEPTH), (0.42 * FRONT_X, CHEST_Y - 0.06 * H, SH_Z + 0.10 * DEPTH))

info = {
    'bones': B,
    'height': H,
    'length': float(Q[:, 1].max() - Q[:, 1].min()),
    'width': float(Q[:, 0].max() - Q[:, 0].min()),
    'front_hip_z': float(SH_Z), 'front_ankle_z': float(fa),
    'rear_hip_z': float(HP_Z), 'rear_ankle_z': float(ra),
    'front_L': float(SH_Z - fa),      # 股関節〜足首。dog_run.py の LEGS に渡す長さ
    'rear_L': float(HP_Z - ra),
}
log("脚の長さ（股関節〜足首）: 前 %.3f ／ 後 %.3f" % (info['front_L'], info['rear_L']))

with open(OUTJ, 'w', encoding='utf-8') as f:
    json.dump(info, f, ensure_ascii=False, indent=1)
log("骨の座標: %s（%d 本）" % (OUTJ, len(B)))

if OUTG:
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.export_scene.gltf(filepath=OUTG, export_format='GLB', use_selection=True, export_yup=True)
    log("そろえたメッシュ: %s (%d バイト)" % (OUTG, os.path.getsize(OUTG)))

with open(os.path.splitext(OUTJ)[0] + '_log.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(LOG))
print("[fit] DONE")
