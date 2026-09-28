# -*- coding: utf-8 -*-
"""犬の走り（襲歩＝ギャロップ）の動きを作る。

   dog_rig.py が保存した dog_rig.blend を読み、IK の足先を置いていって1周ぶんの動きを作る。
   ・ギャロップ：後脚2本 → 前脚2本 の順に蹴り、その間に宙に浮く時間がある
     （はじめトロットで作ったら、脚が短くて歩幅が 0.02 しか出ず「パタパタ」にしか見えなかった。
       宙に浮く時間を作れば、地面を蹴っている時間は1周の 1/4 で済む。
       同じ速さでも 1周 0.67 秒・歩幅 0.30 と、大きくゆったり動かせる）
   ・足首は「股関節を中心にした円の上」に置く。こうすると IK が届かずに固まることがない
   ・胴の高さは、接地している脚の角度から計算する（＝足が地面で滑らない）
   ・その場で走る動き（前へは進まない）。位置は使う側（park12.html / Unity）が動かす

   【注意】Rigify を使うので --factory-startup を付けないこと。

   実行: blender -b -P dog_run.py -- 入力.blend 出力フォルダ [骨の座標.json]
   出力: dog_run.glb（走り Run と飛びかかり Jump の2つ入り）と、コマを並べた絵

   3つめの引数を渡すと、脚の長さ（股関節〜足首）をその JSON から読む（dogfit.py が出したもの）。
   歩幅はこの長さで決まるので、メッシュを入れ替えたら必ず渡すこと。
"""
import bpy, sys, os, math, json, traceback
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(a[0])
OUT = os.path.abspath(a[1])
FIT = os.path.abspath(a[2]) if len(a) > 2 else None
os.makedirs(OUT, exist_ok=True)

LOG = []
def log(s):
    LOG.append(str(s)); print("[run] " + str(s))

# ---------------------------------------------------------------- 動きの寸法
FPS    = 24
FRAMES = 16          # 1周のコマ数（24コマ/秒なので 0.667 秒で1周）
SWING  = 32.0        # 脚を前後に振る角度（片側・度）。これで歩幅が決まる
STANCE = 0.200       # 1周のうち、足が地面に着いている割合
BEND   = 0.93        # 接地中のひざの曲げ（1.0 でまっすぐ）。少し曲げておかないと、
                     # 首や背中を動かした分だけ IK が届かなくなり、足が地面から浮く
TUCK   = 0.30        # 宙にいる間、脚をたたむ量（1.0 で股関節まで縮む）
AIR    = 0.035       # どの脚も着いていない間、胴が上がる高さ
ROLL   = 0.12        # 接地の前後の端で、肉球を浮かせる量（実際の犬も、着く時はつま先から、
                     # 離れる時はかかとから浮く）。これを入れないと、脚を振った端でつま先が
                     # 地面にめり込む。胴の沈みも同じぶん浅くなる
# SWING と BEND は「胴の沈み」を決める。脚を θ 度振ると胴は L(1 - BEND*cosθ) だけ沈むので、
# 脚の短い犬で角度を大きくすると、胸が地面につくほどかがんでしまう（柴の子犬で実際に起きた）。
# そのぶん STANCE を小さく（宙にいる時間を長く）して、1周で進む距離を稼ぐ
FLEX   = 2.5         # 胸の反り（度）。大きくすると肩が上下して足が浮くので、控えめに
NECK   = 7.0         # 首の振り（度）
TAIL   = 14.0        # 尻尾の揺れ（度）
CLIP   = 'Run'

# 脚ごとの「股関節から足首までの長さ」と、1周のどこで着地し始めるか。
# 長さは dog_rig.py の BONES から：前 0.360-0.120＝0.24 / 後ろ 0.390-0.130＝0.26
# ギャロップなので 後ろ→前 の順。左右をわずかにずらすと走りらしく見える
REAR_L, FRONT_L = 0.26, 0.24
if FIT:                                      # dogfit.py が測った長さがあれば、そちらを使う
    with open(FIT, encoding='utf-8') as f:
        _fit = json.load(f)
    REAR_L, FRONT_L = _fit['rear_L'], _fit['front_L']

LEGS = (('foot_ik.L',       REAR_L,  0.00),
        ('foot_ik.R',       REAR_L,  0.06),
        ('front_foot_ik.L', FRONT_L, 0.40),
        ('front_foot_ik.R', FRONT_L, 0.46))

def leg_state(L, phase, p):
    """脚の様子を返す。(前へ振った角度[ラジアン], 縮み具合 r, 接地しているか)"""
    q = (p - phase) % 1.0
    a = math.radians(SWING)
    if q < STANCE:                               # 接地：前へ出した足が、体の下を通って後ろへ流れる
        u = q / STANCE
        return a * (1 - 2 * u), BEND, True
    u = (q - STANCE) / (1 - STANCE)              # 宙：脚をたたんで前へ戻す
    e = u * u * (3 - 2 * u)                      # ゆっくり出て、ゆっくり止まる
    return -a + 2 * a * e, BEND - TUCK * math.sin(math.pi * u), False

def ankle_offset(L, th, r, torso_z):
    """足首の置き場所のずれ（世界の向き。前は -Y、上は +Z）。
       股関節を中心にした半径 r*L の円の上に置くので、IK が届かなくなることがない"""
    return Vector((0.0, -r * L * math.sin(th), torso_z + L - r * L * math.cos(th)))

def torso_curve():
    """1周ぶんの胴の高さ。接地している脚が地面から離れない高さに合わせる。
       （脚を θ 度振ると股関節は L*cosθ までしか上がれない。一番低い方に合わせる）"""
    raw = []
    for f in range(FRAMES):
        p = f / FRAMES
        low = None
        for name, L, ph in LEGS:
            th, r, on = leg_state(L, ph, p)
            if on:
                z = L * (BEND * math.cos(th) - 1) + ROLL * (1 - math.cos(th))
                low = z if low is None else min(low, z)
        raw.append(AIR if low is None else low)   # どの脚も着いていない＝宙に浮いている
    out = list(raw)
    for _ in range(2):                            # コマ間のガタつきをならす（輪なので端はつなげて見る）
        out = [0.25 * out[(i - 1) % FRAMES] + 0.5 * out[i] + 0.25 * out[(i + 1) % FRAMES]
               for i in range(FRAMES)]
    # ならした結果が「接地に必要な高さ」より上に出ると足が浮くので、そこだけ戻す
    return [min(out[i], raw[i]) if raw[i] < 0 else out[i] for i in range(FRAMES)]

# ---------------------------------------------------------------- 読み込み
bpy.ops.wm.open_mainfile(filepath=SRC)
mesh = next((o for o in bpy.context.scene.objects if o.type == 'MESH'), None)
rig = None
if mesh is not None:                                   # メッシュを動かしている方（本生成した rig）を選ぶ
    for m in mesh.modifiers:
        if m.type == 'ARMATURE' and m.object is not None:
            rig = m.object; break
if rig is None:                                        # 念のため：DEF- を持つアーマチュアを探す
    rig = next((o for o in bpy.context.scene.objects if o.type == 'ARMATURE'
                and any(b.name.startswith('DEF-') for b in o.data.bones)), None)
if rig is None or mesh is None:
    log("リグかメッシュが見つからない"); sys.exit(1)
log("読み込み: %s（骨 %d 本）/ %s（頂点 %d）" % (rig.name, len(rig.data.bones), mesh.name, len(mesh.data.vertices)))

sc = bpy.context.scene
sc.render.fps = FPS
sc.frame_start = 1
sc.frame_end = FRAMES

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')

# 骨の「自分の向き」へ、世界の向きのずれを直す
def to_local(pb, world):
    return pb.bone.matrix_local.to_3x3().inverted() @ world

def key_loc(name, frame, world):
    pb = rig.pose.bones.get(name)
    if pb is None: return False
    pb.location = to_local(pb, world)
    pb.keyframe_insert('location', frame=frame)
    return True

def key_rot(name, frame, axis, deg):
    pb = rig.pose.bones.get(name)
    if pb is None: return False
    pb.rotation_mode = 'XYZ'
    v = list(pb.rotation_euler); v['XYZ'.index(axis)] = math.radians(deg)
    pb.rotation_euler = v
    pb.keyframe_insert('rotation_euler', frame=frame)
    return True

TZ = torso_curve()
log("胴の高さ: %.4f〜%.4f（0 が立っている時。マイナスほど沈む）" % (min(TZ), max(TZ)))

missing = []
for f in range(1, FRAMES + 2):                    # 最後のコマは1コマめと同じにして、輪にする
    i = (f - 1) % FRAMES
    p = i / FRAMES
    tz = TZ[i]
    if not key_loc('torso', f, Vector((0, 0, tz))): missing.append('torso')
    for name, L, ph in LEGS:
        th, r, on = leg_state(L, ph, p)
        off = ankle_offset(L, th, r, tz)
        if off.z < 0.0: off.z = 0.0               # 足首は立っている時より下げない
        if not key_loc(name, f, off): missing.append(name)
    # 胸を少しだけ反らせる。胴（torso）は回さない：回すと肩が大きく上下して、前足が地面から浮く
    key_rot('spine.007', f, 'X', FLEX * math.sin(2 * math.pi * p + 1.6))
    # 首と頭は1周に1回振って、走りの上下に合わせて顔が上下するようにする
    key_rot('neck', f, 'X', -NECK * math.sin(2 * math.pi * p - 0.9))
    key_rot('head', f, 'X', -NECK * 0.6 * math.sin(2 * math.pi * p - 0.6))
    # 尻尾は1周に1回、上下に大きく揺らす（巻き尾なので左右には振らない）
    key_rot('spine.001', f, 'X', TAIL * math.sin(2 * math.pi * p))
    key_rot('spine.002', f, 'X', TAIL * 0.7 * math.sin(2 * math.pi * p + 0.6))

if missing:
    log("見つからない骨: " + ", ".join(sorted(set(missing))))
act = rig.animation_data.action
act.name = CLIP
log("打った鍵: %d コマ ×（足4・胴1・首2・尻尾2）" % (FRAMES + 1))

def action_fcurves(act):
    """動きの曲線を取り出す。Blender 4.4 以降は action.fcurves が無く、層の中にある"""
    if hasattr(act, 'fcurves') and len(act.fcurves):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for cb in getattr(strip, 'channelbags', []):
                out.extend(cb.fcurves)
    return out

# なめらかに繋ぐ（輪になるので、コマの間は直線ではなく曲線で）
for fc in action_fcurves(act):
    for kp in fc.keyframe_points:
        kp.interpolation = 'BEZIER'
        kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'

# ---------------------------------------------------------------- 動きを DEF- の骨へ焼く
bpy.ops.pose.select_all(action='SELECT')
try:
    bpy.ops.nla.bake(frame_start=1, frame_end=FRAMES + 1, only_selected=False,
                     visual_keying=True, clear_constraints=False, clear_parents=False,
                     use_current_action=True, bake_types={'POSE'})
    log("焼き込み: できた（IK の結果を、骨そのものの回転に写した）")
except Exception:
    log("焼き込み: 失敗\n" + traceback.format_exc())
bpy.ops.object.mode_set(mode='OBJECT')

# ---------------------------------------------------------------- 足ごとに、地面での動きを測る
# つま先の骨の先端を追いかける。接地している間（低い所にいる間）の前後の動き＝歩幅
TOES = (('左後', 'DEF-toe.L'), ('右後', 'DEF-toe.R'),
        ('左前', 'DEF-front_toe.L'), ('右前', 'DEF-front_toe.R'))
miss = [bn for _, bn in TOES if rig.pose.bones.get(bn) is None]
if miss:                                          # 名前が違う時に備えて、DEF- の一覧を残す
    log("つま先の骨が見つからない: " + ", ".join(miss))
    log("DEF- の骨: " + ", ".join(b.name for b in rig.data.bones if b.name.startswith('DEF-')))
# コマの間も測る。16コマだと接地が3〜5コマしか当たらず、歩幅が短く出てしまう
SUB = 4
track = {k: [] for k, _ in TOES}
lows, low_y = [], []
steps = [1 + i / SUB for i in range(FRAMES * SUB)]
for f in steps:
    sc.frame_set(int(f), subframe=f - int(f))
    bpy.context.view_layer.update()
    for k, bn in TOES:
        pb = rig.pose.bones.get(bn)
        track[k].append(tuple(rig.matrix_world @ pb.tail) if pb else (0, float('nan'), float('nan')))
    if abs(f - round(f)) < 1e-6:                  # 体の低い所は、ふつうのコマだけで足りる
        dg = bpy.context.evaluated_depsgraph_get()
        ev = mesh.evaluated_get(dg); m = ev.to_mesh()
        Pv = np.array([tuple(mesh.matrix_world @ v.co) for v in m.vertices])
        lows.append(Pv[:, 2].min())
        low_y.append(Pv[np.argmin(Pv[:, 2]), 1])
        ev.to_mesh_clear()
log("体の一番低い所: %.4f〜%.4f（0 が地面。マイナスならめり込んでいる）／ その前後位置 %.3f〜%.3f"
    % (min(lows), max(lows), min(low_y), max(low_y)))

strides = []
for k, _ in TOES:
    a = np.array(track[k])
    zmin = np.nanmin(a[:, 2])
    on = a[a[:, 2] < zmin + 0.015]                # 地面の近くにいる所＝接地
    sp = float(on[:, 1].max() - on[:, 1].min()) if len(on) > 1 else 0.0
    strides.append(sp)
    log("%s足：一番低い所 %.4f ／ 接地 %.1f コマ ／ 歩幅 %.3f" % (k, zmin, len(on) / SUB, sp))
stride = float(np.mean(strides))
cycle = FRAMES / FPS
v_anim = stride / (STANCE * cycle)
# 設計値でも出しておく（測った値と大きく違う時は、測り方かコマ数を疑う）
des = float(np.mean([2 * BEND * L * math.sin(math.radians(SWING)) for _, L, _ in LEGS]))
log("設計上の歩幅: %.3f（測った値 %.3f）" % (des, stride))
log("1周 %.3f 秒 ／ 平均の歩幅 %.3f ／ この動きが表している速さ %.2f 単位/秒" % (cycle, stride, v_anim))
log("→ park12.html の DOG_RUN_GAIN は 1/%.2f = %.2f が「足が滑らない」値" % (v_anim, 1.0 / v_anim))

# ---------------------------------------------------------------- コマを並べた絵
cam_d = bpy.data.cameras.new('cam'); cam_d.type = 'ORTHO'; cam_d.ortho_scale = 1.25
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_shadows = True
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('w'); sc.world = w; w.color = (1, 1, 1)
sc.render.resolution_x = 300; sc.render.resolution_y = 240
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, 0))
rig.hide_render = True
az = 90                                                   # 横から見る（脚の運びが一番よく分かる）
d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(8)),
            -math.cos(math.radians(az)) * math.cos(math.radians(8)), math.sin(math.radians(8))))
cam.location = Vector((0, -0.05, 0.36)) + d * 6
cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
shots = [1, 3, 5, 7, 9, 11, 13, 15]
files = []
for f in shots:
    sc.frame_set(f)
    fn = os.path.join(OUT, 'run_%02d.png' % f); files.append(fn)
    sc.render.filepath = fn; bpy.ops.render.render(write_still=True)
imgs = [bpy.data.images.load(f) for f in files]
w_, h_ = imgs[0].size
cols = 4; rows = (len(imgs) + cols - 1) // cols
buf = np.ones((h_ * rows, w_ * cols, 4), dtype=np.float32)
for k, im in enumerate(imgs):
    px = np.empty(w_ * h_ * 4, dtype=np.float32); im.pixels.foreach_get(px)
    r, c = k // cols, k % cols
    buf[(rows - 1 - r) * h_:(rows - r) * h_, c * w_:(c + 1) * w_] = px.reshape(h_, w_, 4)
o_ = bpy.data.images.new('j', w_ * cols, h_ * rows); o_.pixels.foreach_set(buf.ravel())
o_.filepath_raw = os.path.join(OUT, 'check_run.png'); o_.file_format = 'PNG'; o_.save()
log("絵: %s（コマ %s）" % (os.path.join(OUT, 'check_run.png'), ", ".join(map(str, shots))))

# ---------------------------------------------------------------- 飛びかかり（Jump）
# 走りと同じ「股関節を中心にした円」の置き方を使う（IK が届かなくなることがない）。
# 輪にはしない一発の動き。ためる → 蹴る → 伸びて宙に → 前足から着地 → 沈んで受け止める → 立つ
#
# 胴の高さと脚の縮みは組で決めてある。接地しているコマは
#   足首の高さ = 胴の高さ + L(1 - r·cosθ) が 0 になるように r を選んである。
# 宙のコマは足が地面から離れていればよいので、形の良さで決めた。
JUMP_FRAMES = 14                                  # 24コマ毎秒なので 0.583 秒
JUMP_CLIP = 'Jump'
# (コマ, 胴の高さ, 前脚の角度, 前脚の縮み, 後脚の角度, 後脚の縮み, 首, 尻尾)
JUMP_KEYS = (
    ( 1, -0.011,   0, 0.93,    0, 0.93,   0,   0),   # 立っている
    ( 3, -0.040, -14, 0.73,   26, 0.81,  10,  -8),   # ためる（沈んで後脚を体の下へ）
    ( 5,  0.010,  22, 0.95,  -26, 1.00, -12,  10),   # 蹴り出す
    ( 7,  0.140,  42, 0.98,  -44, 0.92, -16,  18),   # 伸びきって宙に
    ( 9,  0.120,  40, 0.90,  -20, 0.72, -10,  14),   # 落ち始め（後脚をたたむ）
    (11, -0.020,  26, 1.00,    6, 0.88,   6,   4),   # 前足から着地
    (12, -0.050,   8, 0.66,   20, 0.73,  14,  -6),   # 沈んで受け止める
    (14, -0.011,   0, 0.93,    0, 0.93,   0,   0),   # 立ちに戻る
)

def build_jump():
    miss = []
    for f, tz, fth, fr, rth, rr, nk, tl in JUMP_KEYS:
        if not key_loc('torso', f, Vector((0, 0, tz))): miss.append('torso')
        for name, L, _ in LEGS:
            front = name.startswith('front')
            th, r = (fth, fr) if front else (rth, rr)
            off = ankle_offset(L, math.radians(th), r, tz)
            if not key_loc(name, f, off): miss.append(name)
        key_rot('neck', f, 'X', nk)
        key_rot('head', f, 'X', nk * 0.6)
        key_rot('spine.007', f, 'X', -tl * 0.25)   # 胸。伸びる時に少し反る
        key_rot('spine.001', f, 'X', tl)
        key_rot('spine.002', f, 'X', tl * 0.7)
    if miss:
        log("見つからない骨（飛びかかり）: " + ", ".join(sorted(set(miss))))
    log("飛びかかり: %d コマ（%.3f 秒）／鍵 %d 組" % (JUMP_FRAMES, JUMP_FRAMES / FPS, len(JUMP_KEYS)))

# ---------------------------------------------------------------- 走りを預けて、飛びかかりを作る
def stash(action, name):
    """動きを NLA の棚に上げる。glTF は「今の動き」と「棚の動き」を別々に書き出す"""
    action.name = name
    tr = rig.animation_data.nla_tracks.new()
    tr.name = name
    tr.strips.new(name, 1, action)
    tr.mute = True                                # 作業中に混ざらないよう止めておく
    rig.animation_data.action = None
    return tr

run_track = stash(act, CLIP)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.transforms_clear()                   # 走りのポーズを消してから作る
build_jump()
jact = rig.animation_data.action
for fc in action_fcurves(jact):                   # コマの間をなめらかに
    for kp in fc.keyframe_points:
        kp.interpolation = 'BEZIER'
        kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
bpy.ops.pose.select_all(action='SELECT')
try:
    bpy.ops.nla.bake(frame_start=1, frame_end=JUMP_FRAMES, only_selected=False,
                     visual_keying=True, clear_constraints=False, clear_parents=False,
                     use_current_action=True, bake_types={'POSE'})
    log("飛びかかりの焼き込み: できた")
except Exception:
    log("飛びかかりの焼き込み: 失敗" + chr(10) + traceback.format_exc())
bpy.ops.object.mode_set(mode='OBJECT')

# 飛びかかりの高さを測る（地面にめり込んでいないか）
jl = []
for f in range(1, JUMP_FRAMES + 1):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(dg); m = ev.to_mesh()
    Pv = np.array([tuple(mesh.matrix_world @ v.co) for v in m.vertices])
    jl.append(float(Pv[:, 2].min()))
    ev.to_mesh_clear()
log("飛びかかりの一番低い所: " + " ".join("%.3f" % v for v in jl))
log("  → 最小 %.4f（0 が地面。マイナスならめり込んでいる）／ 一番高く浮いたコマ %.4f"
    % (min(jl), max(jl)))


# 飛びかかりのコマを並べた絵。宙に 0.19 上がるので、走りより引いて撮る
cam_d.ortho_scale = 1.55
cam.location = Vector((0, -0.05, 0.50)) + d * 6
cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
jshots = [1, 3, 5, 7, 9, 11, 12, 14]
jfiles = []
for f in jshots:
    sc.frame_set(f)
    fn = os.path.join(OUT, 'jump_%02d.png' % f); jfiles.append(fn)
    sc.render.filepath = fn; bpy.ops.render.render(write_still=True)
jimgs = [bpy.data.images.load(f) for f in jfiles]
jw, jh = jimgs[0].size
jcols = 4; jrows = (len(jimgs) + jcols - 1) // jcols
jbuf = np.ones((jh * jrows, jw * jcols, 4), dtype=np.float32)
for k, im in enumerate(jimgs):
    px = np.empty(jw * jh * 4, dtype=np.float32); im.pixels.foreach_get(px)
    r, c = k // jcols, k % jcols
    jbuf[(jrows - 1 - r) * jh:(jrows - r) * jh, c * jw:(c + 1) * jw] = px.reshape(jh, jw, 4)
jo = bpy.data.images.new('j2', jw * jcols, jh * jrows); jo.pixels.foreach_set(jbuf.ravel())
jo.filepath_raw = os.path.join(OUT, 'check_jump.png'); jo.file_format = 'PNG'; jo.save()
log("飛びかかりの絵: %s（コマ %s）" % (os.path.join(OUT, 'check_jump.png'), ", ".join(map(str, jshots))))

stash(jact, JUMP_CLIP)
for tr in rig.animation_data.nla_tracks:
    tr.mute = False

# ---------------------------------------------------------------- 書き出し
# 書き出す範囲を切る。走りの最後のコマは1コマめと同じ（輪のための重複）なので出さない。
# ここを指定しないと 17コマぶん出てしまい、輪にした時に1コマ分もたつく
sc.frame_start = 1
sc.frame_end = FRAMES
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True); rig.select_set(True)
bpy.context.view_layer.objects.active = rig
path = os.path.join(OUT, 'dog_run.glb')
# export_def_bones=True で、操作用の骨を落として DEF- だけにする（動きは焼き直される）
# export_animation_mode='ACTIONS' で、棚に上げた動きをそれぞれ別のクリップとして出す
bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                          export_animations=True, export_skins=True, export_yup=True,
                          export_frame_range=True, export_animation_mode='ACTIONS',
                          export_anim_single_armature=True,
                          export_def_bones=True, export_optimize_animation_size=False)
log("書き出し: %s (%d バイト)" % (path, os.path.getsize(path)))

with open(os.path.join(OUT, 'run_log.txt'), 'w', encoding='utf-8') as f:
    f.write("\n".join(LOG))
print("[run] DONE")
