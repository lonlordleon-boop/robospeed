# -*- coding: utf-8 -*-
"""乳児期の赤ちゃん（くまの着ぐるみ・四つん這い）に骨を入れ、ハイハイの動きを付ける（2026年9月23日）。

   犬の道具（Rigify の四足）は「脚で立つ」前提で、赤ちゃんの「手とひざ・すねで床に着く」形に合わない。
   そこで骨は自分で組む（胴・首・頭・しっぽ、腕3本・脚3本ずつ = 17本）。Rigify を使わないので --factory-startup を付けてよい。

   ・骨の位置は JSON（骨の名前: [根もと, 先, 親]）。生成したメッシュは左右が対称でないので、左右別々に測って書く
   ・重みは自動（熱の計算）。生成メッシュは UV の切れ目で頂点が分かれていて解けないので、溶接したコピーで計算して位置で写す（dog_rig.py と同じ）
   ・動きは「世界の向き」で決める。骨ごとに、休みの姿勢からどれだけ回すかを世界の軸で与え、pose_bone.matrix に入れる
       - 腕と脚は、右手と左ひざ／左手と右ひざ が組になって交互に出る（対角の組）
       - 床に着いている間（STANCE）は、手を床に平らに置いたまま、腕全体を肩まわりに前から後ろへ回す
       - 浮いている間は、ひじを曲げて手を持ち上げ、前へ戻す。脚はひざを少し持ち上げ、すねの先を上げる
       - その場で這う動き（前へは進まない）。進める速さは最後に出す（足が滑らない速さ）
   ・確かめの絵（横・正面、8コマ）と、glb（動き 'Crawl'）を書き出す

   実行: blender -b --factory-startup -P babycrawl.py -- 入力.glb 骨.json 出力.glb 確かめ用の絵の先頭名 [straight]

   straight を付けると、ひじを曲げずに進む（2026年9月23日、「腕を曲げないで進むことできる？」）。
       腕は肩から1本の棒として前後に振る（上腕と前腕を同じだけ回す）。手のひらは床に平らなまま（手首だけ曲がる）
       浮かせる時は、ひじの代わりに ①肩をすくめる（SHRUG）②腕を少し外へ開く（ABD）③肩の側を持ち上げるよう胸を傾ける（ROLL_S）
       ひじを曲げる版の胴の傾き（ROLL）は、振っている腕の側を下げる向きだったので、straight では胸の傾きを振っている側が上がる向きにした
"""
import bpy, sys, os, math, json
import numpy as np
from mathutils import Vector, Matrix, Quaternion

a = sys.argv[sys.argv.index("--") + 1:]
SRC, BJ, OUT, SHOT = [os.path.abspath(x) for x in a[:4]]
STRAIGHT = len(a) > 4 and a[4] == 'straight'
def log(s): print("[crawl] " + str(s))

# ---------------------------------------------------------------- 動きの値
FPS = 24
FRAMES = 24            # 1周 = 1.0秒
STANCE = 0.62          # 手・ひざが床に着いている割合
ARM_STROKE = 0.12      # 手首を前後に動かす幅（片側）。手首の休みの位置を真ん中にする
HAND_LIFT = 0.075      # 浮いている間に手首を持ち上げる高さ
LEG_SWING = 11.0       # 脚をお尻まわりに振る角度（片側・度）
ELBOW_LIFT = 45.0      # 浮いている間にひじを曲げる角度（度）
HAND_DROOP = 8.0       # 浮いている間に手首が垂れる角度（度）。25 度だと指先が床へ 0.088 沈んだ
KNEE_LIFT = 0.035      # 浮いている間にひざを持ち上げる高さ
SHIN_LIFT = 10.0       # 浮いている間にすねの先を上げる角度（度）
BOB = 0.0              # 胴の上下（固定の揺れは足さない。床に着いている手・ひざから毎コマ決める。固定で揺らすと手が床から 0.036 浮いた）
ROLL = 3.0             # 胴の左右の傾き（度）
HEAD_NOD = 3.0         # 頭のうなずき（度）
TAIL_WAG = 18.0        # しっぽを振る角度（度）
SHRUG = 0.03           # straight：浮いている間に肩をすくめる高さ
ABD = 14.0             # straight：浮いている間に腕を外へ開く角度（度）
ROLL_S = 6.0           # straight：振っている腕の側の肩を持ち上げる胸の傾き（度）
KNEE_DOWN = 0.018      # straight：ひざの付け根を下げる量。腕をまっすぐ下へ伸ばすと胸が上がり、ひざが床から 0.9〜1.8cm 浮いた
PHASE = {'arm.L': 0.0, 'leg.R': 0.0, 'arm.R': 0.5, 'leg.L': 0.5}   # 対角の組

# ---------------------------------------------------------------- 読み込み
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
mesh.name = 'baby'
V0 = np.array([tuple(v.co) for v in mesh.data.vertices])
log("メッシュ: 頂点 %d / 高さ %.3f / 前後 %.3f〜%.3f" % (len(V0), V0[:, 2].max(), V0[:, 1].min(), V0[:, 1].max()))

# ---------------------------------------------------------------- 骨を組む
B = json.load(open(BJ, encoding='utf-8'))
arm_d = bpy.data.armatures.new('baby_rig'); rig = bpy.data.objects.new('baby_rig', arm_d)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig; rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_d.edit_bones
for nm, (h, t, par) in B.items():
    b = eb.new(nm); b.head = Vector(h); b.tail = Vector(t)
    b.align_roll(Vector((0, 0, 1)) if abs((Vector(t) - Vector(h)).normalized().z) < 0.9 else Vector((0, -1, 0)))
for nm, (h, t, par) in B.items():
    if par:
        b = eb[nm]; b.parent = eb[par]
        b.use_connect = (Vector(h) - eb[par].tail).length < 1e-4
bpy.ops.object.mode_set(mode='OBJECT')
log("骨: %d 本" % len(arm_d.bones))

# ---------------------------------------------------------------- 重み（溶接したコピーで熱の計算 → 位置で写す）
def weighted_counts(ob):
    cnt = {g.name: 0 for g in ob.vertex_groups}
    names = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        for gg in v.groups:
            if gg.weight > 0.001: cnt[names[gg.group]] += 1
    return cnt

from mathutils import kdtree
tmp = mesh.copy(); tmp.data = mesh.data.copy(); tmp.name = 'weld_tmp'
bpy.context.collection.objects.link(tmp)
bpy.ops.object.select_all(action='DESELECT'); tmp.select_set(True); bpy.context.view_layer.objects.active = tmp
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=1e-4); bpy.ops.object.mode_set(mode='OBJECT')
log("溶接: 頂点 %d → %d" % (len(mesh.data.vertices), len(tmp.data.vertices)))
bpy.ops.object.select_all(action='DESELECT'); tmp.select_set(True); rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
c = weighted_counts(tmp)
log("溶接したコピーの自動ウェイト: 重みの付いた骨 %d / %d" % (sum(1 for v in c.values() if v), len(c)))
if not any(c.values()):
    log("自動ウェイトが1本も付かなかった"); sys.exit(1)
kd = kdtree.KDTree(len(tmp.data.vertices))
for i, v in enumerate(tmp.data.vertices): kd.insert(v.co, i)
kd.balance()
for g in tmp.vertex_groups: mesh.vertex_groups.new(name=g.name)
tn = {g.index: g.name for g in tmp.vertex_groups}
for v in mesh.data.vertices:
    _, i, _ = kd.find(v.co)
    for gg in tmp.data.vertices[i].groups:
        if gg.weight > 0.0005: mesh.vertex_groups[tn[gg.group]].add([v.index], gg.weight, 'REPLACE')
bpy.data.objects.remove(tmp, do_unlink=True)
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type='ARMATURE_NAME')
c = weighted_counts(mesh)
log("重みの付いた頂点: " + ", ".join("%s=%d" % kv for kv in sorted(c.items(), key=lambda x: -x[1])))
orph = sum(1 for v in mesh.data.vertices if sum(g.weight for g in v.groups) < 1e-5)
log("どの骨にも付いていない頂点: %d" % orph)
if orph:
    # 一番近い「付いている頂点」の重みを写す
    have = [v.index for v in mesh.data.vertices if sum(g.weight for g in v.groups) >= 1e-5]
    kd2 = kdtree.KDTree(len(have))
    for k, i in enumerate(have): kd2.insert(mesh.data.vertices[i].co, k)
    kd2.balance()
    for v in mesh.data.vertices:
        if sum(g.weight for g in v.groups) >= 1e-5: continue
        _, k, _ = kd2.find(v.co)
        for gg in mesh.data.vertices[have[k]].groups:
            mesh.vertex_groups[gg.group].add([v.index], gg.weight, 'REPLACE')

# 手首から先は手の骨だけにする。熱の計算は手を前腕と手で分け合い、前腕が回るとひじを支点に指先が床へ沈んだ（-0.088）。
# 前腕の向きに沿って、手首の少し手前（-BLEND）から少し先（+BLEND）で、前腕 → 手 へなじませる
BLEND = 0.035
for side in 'LR':
    fa, hd, ua = 'forearm.' + side, 'hand.' + side, 'upperarm.' + side
    e = Vector(B[fa][0]); wv = Vector(B[fa][1])
    ax = (wv - e); L = ax.length; ax.normalize()
    gi = {g.name: g.index for g in mesh.vertex_groups}
    n = 0
    for v in mesh.data.vertices:
        ws = {mesh.vertex_groups[g.group].name: g.weight for g in v.groups}
        armw = ws.get(fa, 0) + ws.get(hd, 0) + ws.get(ua, 0)
        if armw < 0.5: continue
        t = (Vector(v.co) - e).dot(ax) - L            # 手首からの距離（+ が手の側）
        if t < -BLEND: continue
        k = min(1.0, (t + BLEND) / (2 * BLEND))
        k = k * k * (3 - 2 * k)
        tot = ws.get(fa, 0) + ws.get(hd, 0)
        mesh.vertex_groups[hd].add([v.index], tot * k + ws.get(hd, 0) * (1 - k) if k < 1 else tot, 'REPLACE')
        mesh.vertex_groups[fa].add([v.index], (tot - (tot * k + ws.get(hd, 0) * (1 - k))) if k < 1 else 0.0, 'REPLACE')
        n += 1
    log("手首から先を手の骨へ: %s %d 頂点" % (side, n))

# ---------------------------------------------------------------- 動き
def ease(x): return x * x * (3 - 2 * x)
def limb(phase):
    """戻り値: 振りの割合 s（+1 前 … -1 後ろ）, 浮き u（0〜1）"""
    p = phase % 1.0
    if p < STANCE:                       # 床に着いている：前 → 後ろへ一定の速さ
        return 1 - 2 * p / STANCE, 0.0
    q = (p - STANCE) / (1 - STANCE)      # 浮いている：後ろ → 前へ、なめらかに
    return -1 + 2 * ease(q), math.sin(math.pi * q)

RX = lambda deg: Matrix.Rotation(math.radians(deg), 4, 'X')
RY = lambda deg: Matrix.Rotation(math.radians(deg), 4, 'Y')
RZ = lambda deg: Matrix.Rotation(math.radians(deg), 4, 'Z')
order = []                               # 親から順
def walk(b):
    order.append(b.name)
    for ch in b.children: walk(ch)
for b in arm_d.bones:
    if b.parent is None: walk(b)

# 腕の IK。前後（y）と上下（z）の面で解き、x 軸まわりの回転（度）を返す。ひじは後ろ（+y）へ曲げる
ARM = {}
for side in 'LR':
    S_ = Vector(B['upperarm.' + side][0]); E_ = Vector(B['forearm.' + side][0]); W_ = Vector(B['forearm.' + side][1])
    s2 = lambda v: (v.y, v.z)
    L1 = math.hypot(E_.y - S_.y, E_.z - S_.z); L2 = math.hypot(W_.y - E_.y, W_.z - E_.z)
    ARM[side] = (s2(S_), s2(E_), s2(W_), L1, L2)
    log("腕 %s: 上腕 %.3f・前腕 %.3f・肩から手首 %.3f（伸ばしきると %.3f）" % (side, L1, L2, math.hypot(W_.y - S_.y, W_.z - S_.z), L1 + L2))
def arm_ik(side, dy, dz):
    (sy, sz), (ey, ez), (wy, wz), L1, L2 = ARM[side]
    ty, tz = wy + dy, wz + dz
    vy, vz = ty - sy, tz - sz; d = math.hypot(vy, vz)
    d = min(d, (L1 + L2) * 0.9999)                   # 届かない時はまっすぐ（手首は少し浮く）
    base = math.atan2(vz, vy)
    c = max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)))
    a = math.acos(c)
    cands = [(sy + L1 * math.cos(base + k * a), sz + L1 * math.sin(base + k * a)) for k in (1, -1)]
    ny, nz = max(cands, key=lambda p: p[0])          # ひじは後ろ側
    wy2, wz2 = sy + d * math.cos(base), sz + d * math.sin(base)
    ang = lambda y, z: math.atan2(z, y)
    ua = math.degrees(ang(ny - sy, nz - sz) - ang(ey - sy, ez - sz))
    fa = math.degrees(ang(wy2 - ny, wz2 - nz) - ang(wy - ey, wz - ez))
    return ua, fa

EXTRA = {}

def pose_frame(ph):
    """ph: 1周の中の位置（0〜1）。各骨の「世界の向きでの回し方」と、胴の上下を返す"""
    D = {}; LIFT = {}; UARM = {'L': 0.0, 'R': 0.0}
    for side in ('L', 'R'):
        s, u = limb(ph + PHASE['arm.' + side])
        # 腕は2本の骨の IK（前後と上下の面で解く）。手首の通り道を決めて、ひじの角度はそこから出す。
        # はじめは角度で振っていたが、右腕は休みの姿勢で前腕が14度前へ傾いていて、ひじを曲げても真下を通るだけで手が上がらず、床へ沈んだ
        if STRAIGHT:
            L_ = ARM[side][3] + ARM[side][4]
            (sy_, sz_), _, (wy_, wz_), _, _ = ARM[side]
            a0 = math.degrees(math.atan2(-(wy_ - sy_), sz_ - wz_))       # 休みの姿勢で腕が前へ傾いている角度
            # 振りの中心は肩の真下。休みの傾きを中心に振ると、後ろの端で腕が真下を向いて手が一番低くなり、離す時に床へ 2cm 沈んだ
            th = -math.degrees(math.atan2(ARM_STROKE, L_)) * s + a0
            R_ = RY((ABD if side == 'L' else -ABD) * u) @ RX(th)   # 外へ開く（左は −x、右は +x へ）
            D['upperarm.' + side] = R_; D['forearm.' + side] = R_        # 同じだけ回す = ひじは曲がらない
            D['hand.' + side] = RY((ABD if side == 'L' else -ABD) * u)  # 手のひらは床と平ら。指先を下げると離す時に床へ 2.2cm 沈んだ
            LIFT['upperarm.' + side] = (SHRUG + EXTRA.get('arm.' + side, 0.0)) * u
            UARM[side] = u
        else:
            ua, fa = arm_ik(side, -ARM_STROKE * s, (HAND_LIFT + EXTRA.get('arm.' + side, 0.0)) * u)
            D['upperarm.' + side] = RX(ua)
            D['forearm.' + side] = RX(fa)
            D['hand.' + side] = RX(HAND_DROOP * u)       # 床に着いている間は平らなまま
        s, u = limb(ph + PHASE['leg.' + side])
        th = -LEG_SWING * s
        D['thigh.' + side] = RX(th)
        D['shin.' + side] = RX(SHIN_LIFT * u)        # すねは床に寝たまま。浮く時だけ先を上げる（すねは後ろ +Y を向くので、上げるのは X 軸まわりに正。負にしたら足先が床へ 0.047 沈んだ）
        D['foot.' + side] = RX(SHIN_LIFT * u)
        LIFT['thigh.' + side] = (KNEE_LIFT + EXTRA.get('leg.' + side, 0.0)) * u - (KNEE_DOWN if STRAIGHT else 0.0)
    w = 2 * math.pi * ph
    bob = BOB * math.cos(2 * w)                      # 1周に2回（組が入れ替わるたび）
    if STRAIGHT:
        # 振っている腕の側の肩を上げる（RY の + で左が上がる）
        D['hips'] = RY(ROLL * 0.5 * math.sin(w))
        D['spine'] = RY(ROLL_S * (UARM['L'] - UARM['R']))
    else:
        D['hips'] = RY(ROLL * math.sin(w))
        D['spine'] = RY(ROLL * 0.5 * math.sin(w))
    D['neck'] = Matrix.Identity(4)
    D['head'] = RX(HEAD_NOD * math.cos(2 * w))
    D['tail'] = RZ(TAIL_WAG * math.sin(w))
    return D, LIFT, bob

sc = bpy.context.scene
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = FRAMES
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
pbs = rig.pose.bones
for pb in pbs: pb.rotation_mode = 'QUATERNION'
rest = {b.name: b.matrix_local.copy() for b in arm_d.bones}

def apply(ph, dz=0.0):
    D, LIFT, bob = pose_frame(ph)
    bob += dz
    for pb in pbs: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for nm in order:
        pb = pbs[nm]; M0 = rest[nm]
        R = D.get(nm, Matrix.Identity(4))
        # 根もとの位置：親が動いた後の位置（親の今の行列 × 休みの時の親から見た位置）
        if pb.parent is None:
            head = M0.to_translation() + Vector((0, 0, bob))
        else:
            P0 = rest[pb.parent.name]; Pn = pb.parent.matrix
            head = (Pn @ P0.inverted() @ M0).to_translation()
        head = head + Vector((0, 0, LIFT.get(nm, 0.0)))
        rot = (R.to_3x3() @ M0.to_3x3()).to_4x4()
        pb.matrix = Matrix.Translation(head) @ rot
        bpy.context.view_layer.update()

def eval_verts():
    dg = bpy.context.evaluated_depsgraph_get(); ev = mesh.evaluated_get(dg)
    m = ev.to_mesh(); P = np.array([tuple(v.co) for v in m.vertices]); ev.to_mesh_clear(); return P
hand_idx = {s: np.nonzero((V0[:, 2] < 0.05) & (V0[:, 1] < -0.2) & ((V0[:, 0] < 0) if s == 'L' else (V0[:, 0] > 0)))[0] for s in 'LR'}
knee_idx = {s: np.nonzero((V0[:, 2] < 0.05) & (V0[:, 1] > 0.0) & (V0[:, 1] < 0.45) & ((V0[:, 0] < 0.05) if s == 'L' else (V0[:, 0] > 0.15)))[0] for s in 'LR'}

# 胴の高さは、床に着いている手・ひざから決める（犬と同じ考え方）。
# いったん置いて、床に着いている組の一番低い所を測り、それが床（0）に来るよう全体を上下させる
def contact_dz(ph):
    apply(ph, 0.0)
    P = eval_verts(); zs = []
    for side in 'LR':
        if limb(ph + PHASE['arm.' + side])[1] == 0: zs.append(P[hand_idx[side], 2].min())
        if limb(ph + PHASE['leg.' + side])[1] == 0 and len(knee_idx[side]): zs.append(P[knee_idx[side], 2].min())
    return -min(zs) if zs else 0.0

CLEAR = 0.008          # 浮いている手・ひざは、床からこれだけ離す
def fix_swing(ph, dz):
    """浮いている手・ひざが床に当たるコマだけ、ひじの曲げ・ひざの持ち上げを足す（5度・5mm ずつ）"""
    EXTRA.clear()
    for _ in range(12):
        apply(ph, dz); P = eval_verts(); bad = False
        for side in 'LR':
            s_, u = limb(ph + PHASE['arm.' + side])
            if u > 0 and P[hand_idx[side], 2].min() < CLEAR * u:
                EXTRA['arm.' + side] = min(0.10 if STRAIGHT else 0.06, EXTRA.get('arm.' + side, 0.0) + 0.01); bad = True
            s_, u = limb(ph + PHASE['leg.' + side])
            if u > 0 and len(knee_idx[side]) and P[knee_idx[side], 2].min() < CLEAR * u:
                EXTRA['leg.' + side] = min(0.04, EXTRA.get('leg.' + side, 0.0) + 0.005); bad = True
        if not bad: break
    return dict(EXTRA)

act = bpy.data.actions.new('Crawl'); rig.animation_data_create(); rig.animation_data.action = act
DZ = [contact_dz((f - 1) / FRAMES) for f in range(1, FRAMES + 1)]
log("胴の上下（床に着いている所から決めた）: %+.3f〜%+.3f" % (min(DZ), max(DZ)))
EX = [fix_swing((f - 1) / FRAMES, DZ[f - 1]) for f in range(1, FRAMES + 1)]
log("足したひじ・ひざ: " + ", ".join("%d:%s" % (k + 1, {kk: round(vv, 3) for kk, vv in e.items()}) for k, e in enumerate(EX) if e))
for f in range(1, FRAMES + 2):                    # 最後のコマ = 1コマめ（輪にする）
    EXTRA.clear(); EXTRA.update(EX[(f - 1) % FRAMES])
    apply((f - 1) / FRAMES, DZ[(f - 1) % FRAMES])
    for pb in pbs:
        pb.keyframe_insert('rotation_quaternion', frame=f)
        pb.keyframe_insert('location', frame=f)
bpy.ops.object.mode_set(mode='OBJECT')
log("動き: %d コマ（%.2f 秒）" % (FRAMES, FRAMES / FPS))

# ---------------------------------------------------------------- 測る（手とひざの高さ、手の進む速さ）
rows = []
for f in range(1, FRAMES + 1):
    sc.frame_set(f); P = eval_verts()
    rows.append([P[:, 2].min()] + [P[hand_idx[s], 2].min() for s in 'LR'] + [P[hand_idx[s], 1].mean() for s in 'LR']
                + [P[knee_idx[s], 2].min() if len(knee_idx[s]) else 0 for s in 'LR'])
R_ = np.array(rows)
for f in range(FRAMES):
    log("  コマ %2d: 体 %+.3f / 手 L %+.3f R %+.3f / ひざ L %+.3f R %+.3f" % (f + 1, R_[f, 0], R_[f, 1], R_[f, 2], R_[f, 5], R_[f, 6]))
log("体の一番低い所: %.3f〜%.3f（0 が床）" % (R_[:, 0].min(), R_[:, 0].max()))
log("手の一番低い所 L: %.3f〜%.3f / R: %.3f〜%.3f" % (R_[:, 1].min(), R_[:, 1].max(), R_[:, 2].min(), R_[:, 2].max()))
log("ひざの一番低い所 L: %.3f〜%.3f / R: %.3f〜%.3f（ひざ %d・%d 頂点）" % (R_[:, 5].min(), R_[:, 5].max(), R_[:, 6].min(), R_[:, 6].max(), len(knee_idx['L']), len(knee_idx['R'])))
# 手の前後の動き：床に着いている間に後ろへ動く量 = 1歩
st = int(FRAMES * STANCE)
strideL = R_[:, 3].max() - R_[:, 3].min(); strideR = R_[:, 4].max() - R_[:, 4].min()
speed = ((strideL + strideR) / 2) / (STANCE * FRAMES / FPS)
log("手の前後の幅 L %.3f / R %.3f → 足が滑らない進む速さ ≈ %.3f 単位/秒" % (strideL, strideR, speed))

# ---------------------------------------------------------------- 確かめの絵（横・正面 × 8コマ）
cd = bpy.data.cameras.new('c'); cd.type = 'ORTHO'; cd.ortho_scale = 2.3
cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.view_settings.view_transform = 'Standard'
wd = bpy.data.worlds.new('w'); sc.world = wd; wd.color = (1, 1, 1)
sc.render.resolution_x = 300; sc.render.resolution_y = 300
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
rig.hide_render = True
C = Vector((0, 0, 0.95))
for vname, dv in (('side', Vector((1, 0, 0.08))), ('front', Vector((0, -1, 0.15))), ('q', Vector((0.7, -0.7, 0.45)))):
    dv = dv.normalized(); cam.location = C + dv * 10; cam.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    files = []
    for k, f in enumerate(range(1, FRAMES + 1, FRAMES // 8)):
        sc.frame_set(f); fn = os.path.join(os.path.dirname(SHOT), '_cr_%s_%02d.png' % (vname, k)); files.append(fn)
        sc.render.filepath = fn; bpy.ops.render.render(write_still=True)
    imgs = [bpy.data.images.load(x) for x in files]; W, H = imgs[0].size
    buf = np.ones((H, W * len(imgs), 4), np.float32)
    for k, im in enumerate(imgs):
        px = np.empty(W * H * 4, np.float32); im.pixels.foreach_get(px); buf[:, k * W:(k + 1) * W] = px.reshape(H, W, 4)
    o = bpy.data.images.new('o', W * len(imgs), H); o.pixels.foreach_set(buf.ravel())
    o.filepath_raw = SHOT + '_' + vname + '.png'; o.file_format = 'PNG'; o.save()
    log("絵: " + SHOT + '_' + vname + '.png')
bpy.data.objects.remove(bpy.data.objects['Plane'], do_unlink=True)

# ---------------------------------------------------------------- 書き出し
tr = rig.animation_data.nla_tracks.new(); tr.name = 'Crawl'; tr.strips.new('Crawl', 1, act)
rig.animation_data.action = None
sc.frame_set(1)
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_yup=True,
                          export_animations=True, export_animation_mode='ACTIONS', export_frame_range=True,
                          export_skins=True, export_image_format='AUTO')
log("書き出し: %s (%d バイト)" % (OUT, os.path.getsize(OUT)))
