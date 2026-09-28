# -*- coding: utf-8 -*-
"""公園の遊びの動きを Rigify で作り、今の骨（Meshy の骨）へ焼き戻して、骨だけの glb に書き出す。
   swing_pose.py と同じ骨の合わせ方・焼き戻し方。できる動き:
     Slide_Ride … 滑り台に座り、脚を前へ伸ばして両手を上げる
     Sand_Dig   … しゃがんで両手で交互に砂を掘る（1.5秒のくり返し）
     Sand_Find  … 立って、見つけた物を両手で掲げる
     Climb      … ジャングルジムを登る（1段=1秒のくり返し。体は動かさず、手足だけ段を運ぶ。持ち上げるのは使う側）
     Sing       … 片手をマイクにして、もう片手を振り、体を揺らして歌う（2秒のくり返し）
     Bar_Hang   … 鉄棒にぶら下がる（体を引き上げた形。棒は胸の前・あごの下）
     Bar_Tuck   … ぶら下がったまま膝を抱え込む（跳び下りる間に使う）
     Bar_Kip    … ぶら下がって脚をそろえて前へ振り上げる（蹴上がり用に作った。今は下りの振り出しの予備）
     Bar_Support … つばめ（腕を伸ばし、腰の前の棒の上で体を支える。逆上がり・空中逆上がりで使う）
     Seesaw_Ride … シーソーにまたがって前の握り手を持ち、下がった時に足で地面を蹴る（2秒のくり返し。板を傾けるのは使う側）
     Duel_Ready … 対決の前に意気込む（左手を腰に当て、右手で相手を指す。膝で弾む。1秒のくり返し）
     Pump_Push  … 自転車の空気入れの持ち手を両手で1回押し下げて戻す（0.6秒。持ち手を動かすのは使う側）
     Pump_Surprise … 風船が割れて驚く（のけぞって両手を広げる）
     Beam_Walk  … 細い鉄骨を、両手を広げてそろそろ渡る（その場の足踏み。1.2秒で左右1歩ずつ。進めるのは使う側）
     Beam_Scared … 足がすくんで、腰を落としてぷるぷる震える（0.5秒のくり返し）
     Beam_Fall  … 落ちる（ばんざいして足を縮める）
     Water_Carry … すくった水を両手に持って小走り（両手を胸の前でそろえたまま、小さな歩幅。約0.42秒で左右1歩ずつ。進めるのは使う側で、1.7 m/秒）
     Water_Scoop … 水飲み場の水を両手ですくう（少し前かがみで、鉢の中へ両手を伸ばし、すくって胸の前へ引く。1.2秒のくり返し。鉢の水面は素のモデルの単位で高さ 0.79）
   実行: blender -b --factory-startup -P play_pose.py -- 入力.glb 出力フォルダ 骨だけの動き.glb
   書き出したら、preview/play_clips_data.js へ文字にして埋め込み直すこと。
   確かめ用の絵（各動きを前と横から数コマ）を出力フォルダに描く。"""
import bpy, sys, os, math, addon_utils
import numpy as np
from mathutils import Matrix, Vector, Quaternion

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT, CLIPS_OUT = a[0], os.path.abspath(a[1]), a[2]
ONLY = a[3].split(',') if len(a) > 3 else None     # 確かめ用：作る動きを絞る
os.makedirs(os.path.join(OUT, 'parts'), exist_ok=True)
PAGE_K = 1.377          # park12.html での元気少女の大きさの倍率（素のモデル → 世界）
RUNG = 0.5 / PAGE_K     # ジャングルジムの段の間隔（0.5）を素のモデルの単位に直したもの

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("rigify", default_set=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
if arm.animation_data is None: arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'; pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
def J(n): return arm.matrix_world @ arm.data.bones[n].head_local
V0 = np.array([tuple(mesh.matrix_world @ v.co) for v in mesh.data.vertices])

# ---- Rigify の骨組み（swing_pose.py と同じ合わせ方）----
bpy.ops.object.armature_basic_human_metarig_add()
meta = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
eb = meta.data.edit_bones
for n in ('breast.L', 'breast.R', 'pelvis.L', 'pelvis.R'): eb.remove(eb[n])
def put(n, h, t):
    b = eb[n]; b.use_connect = False; b.head = h; b.tail = t
mid = lambda p, q: p.lerp(q, 0.5)
hips, s02, s01, sp, nk, hd = J('Hips'), J('Spine02'), J('Spine01'), J('Spine'), J('neck'), J('Head')
put('spine', hips, s02); put('spine.001', s02, s01); put('spine.002', s01, sp)
put('spine.003', sp, Vector((nk.x, nk.y, max(nk.z, sp.z + 0.012))))
put('spine.004', eb['spine.003'].tail.copy(), mid(nk, hd)); put('spine.005', mid(nk, hd), hd)
put('spine.006', hd, J('head_end'))
for n in ('spine.001', 'spine.002', 'spine.003', 'spine.005', 'spine.006'): eb[n].use_connect = True
for S, s in (('L', 'Left'), ('R', 'Right')):
    sh, ua, fa, hn = J(s + 'Shoulder'), J(s + 'Arm'), J(s + 'ForeArm'), J(s + 'Hand')
    put('shoulder.' + S, sh, ua); put('upper_arm.' + S, ua, fa); put('forearm.' + S, fa, hn)
    put('hand.' + S, hn, hn + (hn - fa).normalized() * 0.06)
    th, sn, ft, to = J(s + 'UpLeg'), J(s + 'Leg'), J(s + 'Foot'), J(s + 'ToeBase')
    put('thigh.' + S, th, sn); put('shin.' + S, sn, ft); put('foot.' + S, ft, to)
    put('toe.' + S, to, to + Vector((0, -0.045, 0)))
    sx = 1 if S == 'L' else -1
    put('heel.02.' + S, Vector((ft.x - 0.02 * sx, ft.y + 0.03, 0.0)), Vector((ft.x + 0.02 * sx, ft.y + 0.03, 0.0)))
    for n in ('forearm.', 'hand.', 'shin.', 'foot.', 'toe.'): eb[n + S].use_connect = True
bpy.ops.armature.select_all(action='SELECT')
bpy.ops.armature.calculate_roll(type='GLOBAL_NEG_Y')
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.pose.rigify_generate()
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o not in (arm, meta))
P = rig.pose.bones
for S in 'LR':
    P['upper_arm_parent.' + S]['IK_FK'] = 0.0      # 腕は IK
    P['upper_arm_parent.' + S]['pole_vector'] = True
for pb in P: pb.rotation_mode = 'QUATERNION'
upd = bpy.context.view_layer.update
upd()

# ---- 姿勢を作る道具 ----
def wmat(pb): return rig.matrix_world @ pb.matrix
def setw(pb, loc, rot, scl):
    pb.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(loc, rot, scl); upd()
def aim(name, direction, roll=0.0):
    """骨の向き（Y軸）を世界空間の方向へ向け、その向きのまわりに roll 度ひねる"""
    pb = P[name]; loc, rot, scl = wmat(pb).decompose()
    cur = (rot @ Vector((0, 1, 0))).normalized()
    d = Vector(direction).normalized()
    q = cur.rotation_difference(d) @ rot
    if roll: q = Quaternion(d, math.radians(roll)) @ q
    setw(pb, loc, q, scl)
def place(name, pos):
    pb = P[name]; loc, rot, scl = wmat(pb).decompose(); setw(pb, Vector(pos), rot, scl)
def turn(name, axis, deg, move=None):
    pb = P[name]; loc, rot, scl = wmat(pb).decompose()
    setw(pb, loc + (Vector(move) if move else Vector()), Quaternion(Vector(axis), math.radians(deg)) @ rot, scl)
def reset():
    for pb in P:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
    upd()
REST = {n: (rig.matrix_world @ rig.data.bones[n].head_local).copy() for n in ('foot_ik.L', 'foot_ik.R')}
HIPY = float(J('Hips').y)

def pose(spec):
    """spec の中身:
       drop 腰を下げる量 / back 腰を後ろへ引く量 / lean 上体の前傾（度）/ sway 上体の左右の傾き（度、胸だけ）
       legs 'fk' なら thigh/shin/foot の向き（L は x を正、R は鏡写し）、'ik' なら足を素の位置（feet で上書き）に置く
       hands (L, R) の位置、hdir 手の指先の向き、hroll 手のひねり、elbow ひじの目印の位置"""
    reset()
    ik_legs = spec.get('legs') == 'ik'
    for S in 'LR': P['thigh_parent.' + S]['IK_FK'] = 0.0 if ik_legs else 1.0
    upd()
    t = P['torso']; loc, rot, scl = wmat(t).decompose()
    q = Quaternion((1, 0, 0), math.radians(spec.get('lean', 0)))   # キャラは -Y が前。X軸まわりに正に回すと頭が前へ出る
    setw(t, loc + Vector((0, spec.get('back', 0), -spec.get('drop', 0))), q @ rot, scl)
    if spec.get('sway'): turn('chest', (0, 1, 0), spec['sway'])
    for S, sx in (('L', 1), ('R', -1)):
        if ik_legs:
            f = spec.get('feet', {}).get(S)
            place('foot_ik.' + S, f if f else REST['foot_ik.' + S])
            if spec.get('knee'):
                P['thigh_parent.' + S]['pole_vector'] = True
                kx, ky, kz = spec['knee']; place('thigh_ik_target.' + S, (sx * kx, ky, kz))
        else:
            for part in ('thigh', 'shin', 'foot'):
                d = Vector(spec[part]); d.x *= sx
                aim(part + '_fk.' + S, d)
        hx, hy, hz = spec['hands'][S]
        place('hand_ik.' + S, (hx, hy, hz))
        ex, ey, ez = spec.get('elbow', (0.30, 0.20, 0.35))
        place('upper_arm_ik_target.' + S, (sx * ex, ey, ez))
        hd_ = spec.get('hdir', {}).get(S)
        if hd_: aim('hand_ik.' + S, hd_, spec.get('hroll', {}).get(S, 0))
    upd()

# ---- Rigify → 今の骨へ焼き戻す ----
PAIRS = [('Hips', 'ORG-spine'), ('Spine02', 'ORG-spine.001'), ('Spine01', 'ORG-spine.002'), ('Spine', 'ORG-spine.003'),
         ('neck', 'ORG-spine.004'), ('Head', 'ORG-spine.006')]
for S, s in (('L', 'Left'), ('R', 'Right')):
    PAIRS += [(s + 'Shoulder', 'ORG-shoulder.' + S), (s + 'Arm', 'ORG-upper_arm.' + S),
              (s + 'ForeArm', 'ORG-forearm.' + S), (s + 'Hand', 'ORG-hand.' + S),
              (s + 'UpLeg', 'ORG-thigh.' + S), (s + 'Leg', 'ORG-shin.' + S),
              (s + 'Foot', 'ORG-foot.' + S), (s + 'ToeBase', 'ORG-toe.' + S)]
restM = {n: (arm.matrix_world @ arm.data.bones[n].matrix_local).decompose()[1] for n, o in PAIRS}
restO = {o: (rig.matrix_world @ rig.data.bones[o].matrix_local).decompose()[1] for n, o in PAIRS}
hip_off = (rig.matrix_world @ rig.data.bones['ORG-spine'].head_local) - J('Hips')
def bake_to_meshy(frame=None):
    for n, o in PAIRS:
        Mo = rig.matrix_world @ P[o].matrix
        q = Mo.decompose()[1] @ restO[o].inverted() @ restM[n]
        pb = arm.pose.bones[n]
        loc, _, scl = (arm.matrix_world @ pb.matrix).decompose()
        if n == 'Hips': loc = Mo.translation - hip_off
        pb.matrix = arm.matrix_world.inverted() @ Matrix.LocRotScale(loc, q, scl)
        upd()
        if frame is not None:
            pb.keyframe_insert('rotation_quaternion', frame=frame, group=n)
            if n == 'Hips': pb.keyframe_insert('location', frame=frame, group=n)
def posed_mesh():
    dg = bpy.context.evaluated_depsgraph_get(); ev = mesh.evaluated_get(dg); me = ev.to_mesh()
    v = np.array([tuple(ev.matrix_world @ x.co) for x in me.vertices]); ev.to_mesh_clear(); return v
names = {g.index: g.name for g in mesh.vertex_groups}
top = np.array([names[max(v.groups, key=lambda g: g.weight).group] if len(v.groups) else '' for v in mesh.data.vertices])
FEET = np.isin(top, ['LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'])
E = np.array([tuple(e.vertices) for e in mesh.data.edges])
L0 = np.linalg.norm(V0[E[:, 0]] - V0[E[:, 1]], axis=1)
def stretched(Vx):
    L = np.linalg.norm(Vx[E[:, 0]] - Vx[E[:, 1]], axis=1); r = L / np.maximum(L0, 1e-6)
    return int(((r > 2.5) & (L > 0.02)).sum())
def ground_drop(spec, target=0.004):
    """足の一番低い所が地面に着くよう、腰を下げる量を決める（脚の向きは世界で決まっているので、腰と一緒に足も動く）"""
    s = dict(spec); s['drop'] = spec.get('drop', 0)
    pose(s); bake_to_meshy(); low = float(posed_mesh()[FEET][:, 2].min())
    s['drop'] += low - target
    return s['drop']

ACTS = []
def bake_clip(name, frames, fn):
    act = bpy.data.actions.new(name); arm.animation_data.action = act
    worst = 0
    for f in frames:
        fn(f); bake_to_meshy(f)
    arm.animation_data.action = None
    tr = arm.animation_data.nla_tracks.new(); tr.name = name
    st = tr.strips.new(name, frames[0], act)
    ACTS.append((name, act, frames))
    print("PP %s: %d〜%d コマ" % (name, frames[0], frames[-1]))
    return act
want = lambda n: ONLY is None or n in ONLY

# ---- 1. 滑り台：座って脚を前へ、両手を上げる ----
if want('Slide_Ride'):
    SLIDE = dict(drop=0.06, lean=-12, thigh=(0.10, -1, 0.02), shin=(0.10, -1, 0.10), foot=(0.05, -0.45, 1),
                 hands={'L': (0.28, HIPY + 0.02, 0.86), 'R': (-0.28, HIPY + 0.02, 0.86)},
                 elbow=(0.40, 0.10, 0.60), hdir={'L': (0.35, 0, 1), 'R': (-0.35, 0, 1)}, hroll={'L': 0, 'R': 0})
    bake_clip('Slide_Ride', [0, 1], lambda f: pose(SLIDE))

# ---- 2. 砂場：しゃがんで交互に掘る ----
if want('Sand_Dig'):
    SQ = dict(lean=32, thigh=(0.45, -1, -0.12), shin=(0.12, 0.45, -1), foot=(0.15, -1, -0.15),
              elbow=(0.35, 0.10, 0.25), hands={'L': (0.14, -0.28, 0.06), 'R': (-0.14, -0.28, 0.06)},
              hdir={'L': (0.1, -1, -0.8), 'R': (-0.1, -1, -0.8)})
    SQ['drop'] = ground_drop(SQ)
    print("PP しゃがむ深さ %.3f" % SQ['drop'])
    FRD = 36
    def dig(f):
        ph = 2 * math.pi * f / FRD
        s = dict(SQ); hs = {}
        for S, sx, off in (('L', 1, 0.0), ('R', -1, math.pi)):
            c = math.sin(ph + off)            # +: 手を下げて手前へかき寄せる / -: 持ち上げて前へ戻す
            z = 0.05 + 0.09 * max(0.0, -c)
            y = -0.30 + 0.10 * (1 - math.cos(ph + off)) / 2
            hs[S] = (sx * 0.14, y, z)
        s['hands'] = hs
        s['sway'] = 4 * math.sin(ph)
        pose(s)
    bake_clip('Sand_Dig', list(range(0, FRD + 1)), dig)

# ---- 3. 見つけた物を掲げる ----
if want('Sand_Find'):
    # 頭が大きく腕が短いので、頭の前では両手が届かない。頭の横で両手を上げる「やったー」にする
    FIND = dict(legs='ik', drop=0.0, lean=-6, hands={'L': (0.30, -0.12, 0.74), 'R': (-0.30, -0.12, 0.74)},
                elbow=(0.40, 0.05, 0.50), hdir={'L': (0.3, -0.2, 1), 'R': (-0.3, -0.2, 1)})
    bake_clip('Sand_Find', [0, 1], lambda f: pose(FIND))

# ---- 4. ジャングルジムを登る（その場で手足だけ段を運ぶ）----
if want('Climb'):
    FRC = 24
    BAR_Y = -0.24             # 横棒の前後（体の前）
    D = RUNG
    HAND_HI, FOOT_HI = 0.76, 0.30
    LIMBS = [('hand', 'R', 0.00), ('foot', 'L', 0.25), ('hand', 'L', 0.50), ('foot', 'R', 0.75)]
    def limb_z(hi, u):
        """u: その手足の周期の中の位置。最初の4分の1で1段上へ運び、残りは体が上がるぶん下がって見える"""
        if u < 0.25:
            k = u / 0.25
            return hi - 0.75 * D + 0.75 * D * (k * k * (3 - 2 * k)), math.sin(math.pi * k)
        return hi - (u - 0.25) * D, 0.0
    def climb(f):
        p = f / FRC
        s = dict(legs='ik', drop=-0.02, lean=8, elbow=(0.32, 0.05, 0.40), knee=(0.30, -0.35, 0.30))
        hs, fs = {}, {}
        for kind, S, st in LIMBS:
            sx = 1 if S == 'L' else -1
            u = (p - st) % 1.0
            if kind == 'hand':
                z, lift = limb_z(HAND_HI, u)
                hs[S] = (sx * 0.17, BAR_Y + 0.07 * lift, z)
            else:
                z, lift = limb_z(FOOT_HI, u)
                fs[S] = (sx * 0.10, BAR_Y + 0.04 + 0.06 * lift, z)
        s['hands'] = hs; s['feet'] = fs
        s['hdir'] = {'L': (0.1, -0.6, 1), 'R': (-0.1, -0.6, 1)}
        s['hroll'] = {'L': 270, 'R': 180}
        s['sway'] = 5 * math.sin(2 * math.pi * p)
        pose(s)
    bake_clip('Climb', list(range(0, FRC + 1)), climb)

# ---- 5. 歌う ----
if want('Sing'):
    FRS = 48
    def sing(f):
        ph = 2 * math.pi * f / FRS
        s = dict(legs='ik', drop=0.012 * (1 - math.cos(2 * ph)) / 2, lean=-4, sway=7 * math.sin(ph),
                 elbow=(0.30, 0.15, 0.40))
        s['hands'] = {'R': (-0.05, -0.34, 0.62), 'L': (0.36, -0.10, 0.62 + 0.12 * math.sin(2 * ph))}
        s['hdir'] = {'R': (0.05, -0.2, 1), 'L': (0.6, -0.1, 0.6 + 0.4 * math.sin(2 * ph))}
        s['hroll'] = {'R': 180, 'L': 0}
        pose(s)
    bake_clip('Sing', list(range(0, FRS + 1)), sing)

# ---- 6. 鉄棒：ぶら下がる／膝を抱える ----
# 1回目は頭の横で握ったが、左右の手をつなぐ棒が首の後ろを通った（頭が大きく、頭の上や顔の前には手が届かない）。
# そこで、懸垂で体を引き上げた形にして、棒を胸の前・あごの下で握る。
# 素のモデルで、高さ0.50の胸の前端は y=-0.186、あごの下は高さ0.625。棒は高さ0.52、胸の0.05前
BAR_HANDS = {'L': (0.17, -0.24, 0.52), 'R': (-0.17, -0.24, 0.52)}
BAR_HDIR = {'L': (0.15, -1, 0.1), 'R': (-0.15, -1, 0.1)}
if want('Bar_Hang'):
    HANG = dict(drop=0.0, lean=-4, thigh=(0.04, -0.12, -1), shin=(0.03, 0.12, -1), foot=(0.02, -0.5, -1),
                hands=BAR_HANDS, elbow=(0.30, 0.10, 0.35), hdir=BAR_HDIR)
    bake_clip('Bar_Hang', [0, 1], lambda f: pose(HANG))
if want('Bar_Tuck'):
    TUCK = dict(drop=0.0, lean=10, thigh=(0.12, -1, 0.35), shin=(0.06, 0.25, -1), foot=(0.03, -0.8, -0.6),
                hands=BAR_HANDS, elbow=(0.30, 0.10, 0.35), hdir=BAR_HDIR)
    bake_clip('Bar_Tuck', [0, 1], lambda f: pose(TUCK))
# つばめ（腰の位置で棒に乗る）。前回りの前かがみ（Bar_Pike）は使わなくなったので外した。
# 素のモデルで腰は高さ0.37、肩は (0.109, -0.077, 0.56)、肩から手首まで約0.26。
# つばめの棒は腰の前（高さ0.37、y=-0.25）。上体を少し前へ倒すと腕がほぼまっすぐ届く
SUP_HANDS = {'L': (0.17, -0.25, 0.37), 'R': (-0.17, -0.25, 0.37)}
SUP_HDIR = {'L': (0.1, -1, -0.3), 'R': (-0.1, -1, -0.3)}
if want('Bar_Kip'):
    # 蹴上がりの途中：ぶら下がったまま脚をそろえて振り上げ、足首を棒に引き寄せる（お手本の動画の形）。
    # 足首は棒（y=-0.24、高さ0.52）の少し前・少し下。使う側で体ごと後ろへ倒すと、腰が棒の真下に来る
    # 1回目は足先を棒の 0.1 下までにしたが、脚の上げ方が浅かった
    # 足首の位置を IK で決めると膝がねじれて服が伸びたので、脚をまっすぐ伸ばして足首が棒の前下（約0.1離れる）に来る向きにする
    KIP = dict(drop=0.0, lean=-6, thigh=(0.0, -0.95, 0.31), shin=(0.0, -0.95, 0.31), foot=(0.02, -1, 0.3),
               hands=BAR_HANDS, elbow=(0.30, 0.10, 0.35), hdir=BAR_HDIR)
    bake_clip('Bar_Kip', [0, 1], lambda f: pose(KIP))
if want('Bar_Support'):
    # つばめ：腕を伸ばして棒の上で体を支え、脚は少し後ろへ
    SUP = dict(drop=0.0, lean=14, thigh=(0.03, 0.12, -1), shin=(0.02, 0.08, -1), foot=(0.02, -0.6, -1),
               hands=SUP_HANDS, elbow=(0.30, 0.25, 0.45), hdir=SUP_HDIR)
    bake_clip('Bar_Support', [0, 1], lambda f: pose(SUP))
# ---- 7. シーソー：またがって握り手を持ち、下がった時に地面を蹴る ----
# 握り手は座る所の 0.25 前・板の上 0.265（世界の単位）。素のモデルの単位に直して置く
if want('Seesaw_Ride'):
    FRW = 48
    GRIP_Y = HIPY - 0.25 / PAGE_K - 0.02
    GRIP_Z = 0.19 + 0.265 / PAGE_K
    def seesaw(f):
        ph = 2 * math.pi * f / FRW
        w = max(0.0, math.sin(ph))            # 1: 自分の側が一番下（足で蹴る）
        u = max(0.0, -math.sin(ph))           # 1: 一番上（足がぶらぶら）
        s = dict(drop=0.06, lean=8 + 8 * w - 4 * u,
                 thigh=(0.38, -1, -0.30 - 0.15 * w), shin=(0.12, 0.30 - 0.75 * w + 0.15 * u, -1), foot=(0.05, -1, -0.3 + 0.3 * u),
                 hands={'L': (0.09, GRIP_Y, GRIP_Z), 'R': (-0.09, GRIP_Y, GRIP_Z)},
                 elbow=(0.35, 0.10, 0.30), hdir={'L': (0.1, -0.4, 1), 'R': (-0.1, -0.4, 1)}, hroll={'L': 270, 'R': 180})
        pose(s)
    bake_clip('Seesaw_Ride', list(range(0, FRW + 1)), seesaw)

# ---- 8. 対決：意気込む／空気入れを押す／風船が割れて驚く ----
# 頭が大きく腕が短いので、手は頭の横まで（Sand_Find と同じ高さ 0.74 くらいが上限）
if want('Duel_Ready'):
    # 意気込む：左手を腰に当て、右手で相手をびしっと指す。膝で小さく弾む（1秒のくり返し）
    # 1回目は右のこぶしを頭の横で突き上げたが、指の骨が無くこぶしが作れず、頬に手を当てているように見えた
    FRR = 24
    def ready(f):
        ph = 2 * math.pi * f / FRR
        b = (1 - math.cos(ph)) / 2                # 0→1→0：沈んで戻る
        s = dict(legs='ik', drop=0.025 * b, lean=8 + 3 * b, sway=-3, elbow=(0.42, -0.04, 0.42), knee=(0.12, -0.30, 0.20))   # ひじは真横へ（後ろだとリュックに刺さる）
        s['hands'] = {'R': (-0.17, -0.33, 0.56 + 0.015 * b), 'L': (0.15, -0.03, 0.40)}   # 左手は肩から近めに置き、ひじを横へ張る
        s['hdir'] = {'R': (-0.1, -1, 0.05), 'L': (-0.3, 0.2, -1)}
        s['hroll'] = {'R': 180, 'L': 0}
        pose(s)
    bake_clip('Duel_Ready', list(range(0, FRR + 1)), ready)
# 空気入れの持ち手は体の前（y=-0.22）。押す前は胸の高さ 0.45、押し切ると腰の下 0.27。1回押して戻る（0.6秒）
PUMP_Y = -0.22
if want('Pump_Push'):
    FRP = 14
    def pump(f):
        u = f / FRP
        # k: 0（持ち手が上）→ 1（押し切り）。最初の3割で押し下げ、6割半までで戻し、あとは上で持つ
        k = math.sin(math.pi / 2 * min(1.0, u / 0.3)) if u < 0.3 else max(0.0, math.cos(math.pi / 2 * (u - 0.3) / 0.35)) if u < 0.65 else 0.0
        z = 0.45 - 0.18 * k
        s = dict(legs='ik', drop=0.07 * k, lean=10 + 22 * k, elbow=(0.30, 0.05, 0.28), knee=(0.12, -0.35, 0.18))
        s['hands'] = {'L': (0.05, PUMP_Y, z), 'R': (-0.05, PUMP_Y, z)}
        s['hdir'] = {'L': (-0.2, -1, -0.2), 'R': (0.2, -1, -0.2)}
        s['hroll'] = {'L': 270, 'R': 180}
        pose(s)
    bake_clip('Pump_Push', list(range(0, FRP + 1)), pump)
if want('Pump_Surprise'):
    # 割れて驚く：上体を後ろへ反らし、両手を頭の横へぱっと広げる
    SURP = dict(legs='ik', drop=0.01, lean=-12, elbow=(0.42, 0.10, 0.45),
                hands={'L': (0.32, -0.08, 0.66), 'R': (-0.32, -0.08, 0.66)},
                hdir={'L': (0.5, -0.4, 1), 'R': (-0.5, -0.4, 1)})
    bake_clip('Pump_Surprise', [0, 1], lambda f: pose(SURP))

# ---- 9. 鉄骨あみだ：細い鉄骨をそろそろ渡る／足がすくむ／落ちる ----
# 足は一本の線の上に置く（x をほぼ0に寄せる）。その場で足踏みするだけで、前へ進めるのは使う側
if want('Beam_Walk'):
    # 両手を横へ広げてバランスを取り、小さな歩幅でそろそろ進む（1.2秒で左右1歩ずつ）
    FRB = 28
    def beam(f):
        ph = 2 * math.pi * f / FRB
        s = dict(legs='ik', drop=0.03, lean=10, sway=5 * math.sin(ph), elbow=(0.40, 0.05, 0.50), knee=(0.10, -0.35, 0.20))
        fs = {}
        for S, sx, off in (('L', 1, 0.0), ('R', -1, math.pi)):
            fx, fy, fz = REST['foot_ik.' + S]
            u = ph + off
            fs[S] = (sx * 0.035, fy - 0.06 * math.cos(u), fz + 0.035 * max(0.0, math.sin(u)))   # 前へ出す足だけ少し上げる
        s['feet'] = fs
        s['hands'] = {'L': (0.36, -0.04, 0.46 + 0.03 * math.sin(ph)), 'R': (-0.36, -0.04, 0.46 - 0.03 * math.sin(ph))}
        s['hdir'] = {'L': (1, -0.1, 0.1), 'R': (-1, -0.1, 0.1)}
        pose(s)
    bake_clip('Beam_Walk', list(range(0, FRB + 1)), beam)
if want('Beam_Scared'):
    # 足がすくむ：膝を曲げて腰を落とし、両手を広げたままぷるぷる震える（0.5秒のくり返し）
    FRQ = 12
    def scared(f):
        ph = 2 * math.pi * f / FRQ
        w = math.sin(ph)
        s = dict(legs='ik', drop=0.07, lean=16, sway=6 * w, elbow=(0.40, 0.05, 0.45), knee=(0.12, -0.35, 0.18))
        s['feet'] = {S: (sx * 0.035, REST['foot_ik.' + S][1], REST['foot_ik.' + S][2]) for S, sx in (('L', 1), ('R', -1))}
        s['hands'] = {'L': (0.34, -0.10, 0.44 + 0.04 * w), 'R': (-0.34, -0.10, 0.44 - 0.04 * w)}
        s['hdir'] = {'L': (1, -0.3, 0.2), 'R': (-1, -0.3, 0.2)}
        pose(s)
    bake_clip('Beam_Scared', list(range(0, FRQ + 1)), scared)
if want('Beam_Fall'):
    # 落ちる：両手を上へばんざいし、膝を曲げて足を縮める
    FALL = dict(drop=0.0, lean=-10, thigh=(0.16, -1, -0.45), shin=(0.05, 0.35, -1), foot=(0.03, -0.9, -0.4),   # 太ももを前へ上げて膝を曲げる
                hands={'L': (0.30, -0.02, 0.74), 'R': (-0.30, -0.02, 0.74)}, elbow=(0.42, 0.10, 0.45),
                hdir={'L': (0.4, 0, 1), 'R': (-0.4, 0, 1)})
    bake_clip('Beam_Fall', [0, 1], lambda f: pose(FALL))

# ---- 水飲み場で水をくむ ----
# 水飲み場の水面は世界で高さ 1.085（素のモデルの単位で 0.79）、鉢の半径は 0.38（同 0.28）。子は鉢のすぐ手前に立つ（使う側が、鉢の中心から 0.62 の所まで寄せる）。
# 頭が大きく腕が短いので、顔の前へは手が届かない（腕が頭の後ろへ回ってしまう）。Sand_Find と同じく頭の横から両手を上げ、背の高い鉢のふちに手をかけて、中へ入れてすくう
if want('Water_Scoop'):
    FRW2 = 28
    def scoop(f):
        ph = 2 * math.pi * f / FRW2
        k = (1 - math.cos(ph)) / 2                  # 0: 水の中へ両手を伸ばしている / 1: すくって胸の前へ引いた
        y = -0.31 + 0.09 * k
        z = 0.455 + 0.07 * k
        s = dict(legs='ik', drop=0.02 * (1 - k), lean=24 - 10 * k, elbow=(0.30, 0.02, 0.30), knee=(0.12, -0.35, 0.18))
        s['hands'] = {'L': (0.05, y, z), 'R': (-0.05, y, z)}
        s['hdir'] = {'L': (-0.25, -1, 0.15), 'R': (0.25, -1, 0.15)}
        pose(s)
    bake_clip('Water_Scoop', list(range(0, FRW2 + 1)), scoop)

# ---- 水を両手に持って小走り ----
# すくった水をこぼさないよう、両手を胸の前でそろえたまま、小さな歩幅で走る（その場の足踏み。10コマ＝約0.42秒で左右1歩ずつ。進めるのは使う側）。
# 足の前後の振れは ±0.13（素のモデルの単位）。足が滑って見えない速さは 4×0.13÷0.417秒 ≒ 1.25（世界では 1.7 m/秒）
if want('Water_Carry'):
    FRK = 10
    def carry(f):
        ph = 2 * math.pi * f / FRK
        s = dict(legs='ik', drop=0.02 + 0.012 * math.cos(2 * ph), lean=9, sway=2.5 * math.sin(ph), elbow=(0.30, 0.02, 0.30), knee=(0.10, -0.35, 0.20))
        fs = {}
        for S, sx, off in (('L', 1, 0.0), ('R', -1, math.pi)):
            fx, fy, fz = REST['foot_ik.' + S]
            u = ph + off
            fs[S] = (sx * 0.05, fy - 0.13 * math.cos(u), fz + 0.013 + 0.075 * max(0.0, math.sin(u)))   # 前へ出す足だけ上げる（+0.013：脚を後ろへ伸ばした時につま先が地面へ沈むぶん）
        s['feet'] = fs
        b = 0.006 * math.cos(2 * ph)                 # 手はほとんど揺らさない（水を持っているので）
        s['hands'] = {'L': (0.05, -0.215, 0.525 + b), 'R': (-0.05, -0.215, 0.525 + b)}
        s['hdir'] = {'L': (-0.25, -1, 0.15), 'R': (0.25, -1, 0.15)}
        pose(s)
    bake_clip('Water_Carry', list(range(0, FRK + 1)), carry)

# ---- 確かめ：伸びた辺と、足の低さ ----
for name, act, frames in ACTS:
    arm.animation_data.action = act
    worst, low = 0, 9
    for f in frames[::max(1, len(frames) // 8)]:
        bpy.context.scene.frame_set(f); upd()
        V = posed_mesh(); worst = max(worst, stretched(V)); low = min(low, float(V[FEET][:, 2].min()))
    print("PP %-10s 伸びた辺 最大%d本 足の一番低い所 %.3f" % (name, worst, low))
arm.animation_data.action = None

# ---- 確かめの絵 ----
sc = bpy.context.scene
cam_d = bpy.data.cameras.new('cam'); cam_d.type = 'ORTHO'
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.display.shading.show_shadows = True
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('w'); sc.world = w; w.color = (1, 1, 1)
sc.render.resolution_x = 300; sc.render.resolution_y = 360
bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0, 0))
gr = bpy.context.active_object; gm = bpy.data.materials.new('g'); gm.diffuse_color = (0.8, 0.78, 0.72, 1); gr.data.materials.append(gm)
for o in (rig, meta, arm): o.hide_render = True
def shoot(path, center, width, az, el):
    cam_d.ortho_scale = width
    d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
    cam.location = Vector(center) + d * 6
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)
def join(files, outp, cols):
    imgs = [bpy.data.images.load(f) for f in files]
    w_, h_ = imgs[0].size; rows = (len(imgs) + cols - 1) // cols
    buf = np.ones((h_ * rows, w_ * cols, 4), dtype=np.float32)
    for k, im in enumerate(imgs):
        px = np.empty(w_ * h_ * 4, dtype=np.float32); im.pixels.foreach_get(px)
        r_, c_ = rows - 1 - k // cols, k % cols
        buf[r_ * h_:(r_ + 1) * h_, c_ * w_:(c_ + 1) * w_] = px.reshape(h_, w_, 4)
    o_ = bpy.data.images.new('j', w_ * cols, h_ * rows); o_.pixels.foreach_set(buf.ravel())
    o_.filepath_raw = outp; o_.file_format = 'PNG'; o_.save()
for name, act, frames in ACTS:
    arm.animation_data.action = act
    picks = frames[:1] if len(frames) <= 2 else [frames[int(i * (len(frames) - 1) / 4)] for i in range(4)]
    files = []
    for tag, az in (('f', 20), ('s', 90)):
        for f in picks:
            sc.frame_set(f); upd()
            fn = os.path.join(OUT, 'parts', '%s_%s_%02d.png' % (name, tag, f)); files.append(fn)
            shoot(fn, (0, -0.05, 0.55), 1.35, az, 8)
    join(files, os.path.join(OUT, 'check_%s.png' % name), len(picks))
arm.animation_data.action = None

# ---- 骨だけの glb に書き出す ----
for tr in arm.animation_data.nla_tracks:
    tr.mute = False
    for st_ in tr.strips: st_.mute = False
for o in bpy.data.objects: o.select_set(o == arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.gltf(filepath=CLIPS_OUT, export_format='GLB', use_selection=True,
                          export_animations=True, export_animation_mode='NLA_TRACKS',
                          export_skins=False, export_yup=True)
print("PP 書き出し", CLIPS_OUT, os.path.getsize(CLIPS_OUT))
