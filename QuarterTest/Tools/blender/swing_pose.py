# -*- coding: utf-8 -*-
"""Rigify でブランコに座る姿勢と、こぐ動き（2秒のくり返し）を作り、今の骨（Meshy の骨）へ焼き戻す。
   - 手は IK で鎖をつかむ位置に置く。脚は FK で向きを決める
   - 焼き戻した動きで、今のモデル（v55 の重みのまま）を動かして描く
   実行: blender -b --factory-startup -P swing_pose.py -- 入力.glb 出力フォルダ 左手のひねり 右手のひねり [骨だけの動き.glb]
     元気少女 v55 は 左手 270・右手 180（4通りずつ描いて決めた。3つ目を省いて4つ目に test と書くと右手を試し描き）
     5つ目を渡すと、揺れを含まない動きを骨だけの glb に書き出して終わる（preview/swing_clips_data.js の元）。
     書き出したら、preview/swing_clips_data.js へ文字にして埋め込み直すこと"""
import bpy, sys, os, math, addon_utils
import numpy as np
from mathutils import Matrix, Vector, Quaternion

a = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = a[0], os.path.abspath(a[1])
os.makedirs(os.path.join(OUT, 'parts'), exist_ok=True)
ROLL = float(a[2]) if len(a) > 2 else 0.0      # 左手を骨の向きのまわりにひねる角度
ROLLTEST = len(a) > 3 and a[3] == 'test'      # 右手の角度を4通り試す
ROLL_R = float(a[3]) if len(a) > 3 and not ROLLTEST else ROLL   # 右手のひねり
CLIPS_OUT = a[4] if len(a) > 4 else None   # 指定すると、揺れを含まない動きを骨だけの glb に書き出す（ブランコの揺れは使う側で付ける）
FR = 48                 # 1往復のコマ数（24コマ/秒で2秒）
SWING = 22.0            # 振れ幅（度）
BAR_Z = 1.55            # 上の横棒の高さ

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("rigify", default_set=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
old_acts = list(bpy.data.actions)
if arm.animation_data is None: arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'; pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
def J(n): return arm.matrix_world @ arm.data.bones[n].head_local
V0 = np.array([tuple(mesh.matrix_world @ v.co) for v in mesh.data.vertices])

# ---- Rigify の骨組み（rigify_try.py と同じ合わせ方）----
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
    P['upper_arm_parent.' + S]['IK_FK'] = 0.0    # 腕は IK（手の位置で決める）
    P['upper_arm_parent.' + S]['pole_vector'] = True  # ひじの向きは目印の骨で決める
    P['thigh_parent.' + S]['IK_FK'] = 1.0         # 脚は FK（向きで決める）
for pb in P: pb.rotation_mode = 'QUATERNION'
upd = bpy.context.view_layer.update
upd()

# ---- 体の大きさを測る ----
CHAIN_Y = float(J('Hips').y)
sl = V0[(V0[:, 2] > 0.62) & (np.abs(V0[:, 1] - CHAIN_Y) < 0.06)]
head_half = float(np.abs(sl[:, 0]).max())
CHAIN_X = max(head_half + 0.025, 0.22)           # 鎖は、鎖が通る面での頭と髪の外側を通す
GRIP_Z = 0.50                                    # つかむ高さ（座った状態で）
print("SW 頭の半幅 %.3f → 鎖の左右 %.3f" % (head_half, CHAIN_X))

# ---- 姿勢を作る道具 ----
def wmat(pb): return rig.matrix_world @ pb.matrix
def aim(name, direction):
    """骨の向き（Y軸）を世界空間の方向へ向ける。ねじれは素の姿勢から最小の回転で決める"""
    pb = P[name]
    M = wmat(pb); loc, rot, scl = M.decompose()
    cur = (rot @ Vector((0, 1, 0))).normalized()
    q = cur.rotation_difference(Vector(direction).normalized())
    pb.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(loc, q @ rot, scl)
    upd()
def place(name, pos, rot=None):
    pb = P[name]; loc, r0, scl = wmat(pb).decompose()
    pb.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(Vector(pos), rot or r0, scl)
    upd()
def reset():
    for pb in P:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
    upd()
def lerp3(p, q, k): return Vector(p).lerp(Vector(q), k)
LEG_TUCK = dict(thigh=(0.10, -1, -0.05), shin=(0.02, 0.45, -1), foot=(0, -1, -0.7))   # 後ろへ振るとき：脚をたたむ
LEG_SIT  = dict(thigh=(0.10, -1, -0.05), shin=(0.03, -0.15, -1), foot=(0, -1, -0.35))  # ふつうに座る
LEG_EXT  = dict(thigh=(0.10, -1, 0.18), shin=(0.04, -1, 0.40), foot=(0, -1, 0.35))     # 前へ振るとき：脚を伸ばす

def pose(theta, legk, drop, lean):
    """theta: 振れの角度（度、+で後ろ）、legk: 0=たたむ 1=伸ばす（None なら座るだけ）、drop: 腰を下げる量、lean: 上体の傾き（度、+で前）"""
    reset()
    # 腰を下げ、上体を傾ける（torso は腰から上をまとめて動かす）
    t = P['torso']; loc, rot, scl = wmat(t).decompose()
    q = Quaternion((1, 0, 0), math.radians(-lean))
    t.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(loc + Vector((0, 0, -drop)), q @ rot, scl)
    upd()
    for S, sx in (('L', 1), ('R', -1)):
        if legk is None: L = LEG_SIT
        else: L = {k: lerp3(LEG_TUCK[k], LEG_EXT[k], legk) for k in LEG_TUCK}
        for part in ('thigh', 'shin', 'foot'):
            d = Vector(L[part]); d.x *= sx
            aim(part + '_fk.' + S, d)
        # 手：鎖をつかむ。ひじの目印は後ろ下
        place('hand_ik.' + S, (sx * (CHAIN_X - 0.02), CHAIN_Y + 0.005, GRIP_Z - drop * 0.3 - 0.035))
        place('upper_arm_ik_target.' + S, (sx * (CHAIN_X + 0.05), CHAIN_Y + 0.25, GRIP_Z - 0.15))
    # 手の向き：指先を上へ（鎖を握る向き）
    for S, sx in (('L', 1), ('R', -1)):
        aim('hand_ik.' + S, (sx * 0.15, -0.25, 1))
        hp = P['hand_ik.' + S]; loc, rot, scl = wmat(hp).decompose()
        yax = rot @ Vector((0, 1, 0))
        qr = Quaternion(yax, math.radians(ROLL if S == 'L' else ROLL_R))   # 左右の骨は向きが鏡写しでないので、角度は別々に決める
        hp.matrix = rig.matrix_world.inverted() @ Matrix.LocRotScale(loc, qr @ rot, scl); upd()
    # 全体をブランコの支点で回す
    piv = Vector((0, CHAIN_Y, BAR_Z))
    R = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(theta), 4, 'X') @ Matrix.Translation(-piv)
    P['root'].matrix = rig.matrix_world.inverted() @ R @ (rig.matrix_world @ rig.data.bones['root'].matrix_local)
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
    for n, o in PAIRS:          # PAIRS は親から子の順
        Mo = rig.matrix_world @ P[o].matrix
        q = Mo.decompose()[1] @ restO[o].inverted() @ restM[n]
        pb = arm.pose.bones[n]
        Mw = arm.matrix_world @ pb.matrix
        loc, _, scl = Mw.decompose()
        if n == 'Hips': loc = Mo.translation - hip_off
        pb.matrix = arm.matrix_world.inverted() @ Matrix.LocRotScale(loc, q, scl)
        upd()
        if frame is not None:
            pb.keyframe_insert('rotation_quaternion', frame=frame, group=n)
            if n == 'Hips': pb.keyframe_insert('location', frame=frame, group=n)

def posed_mesh():
    dg = bpy.context.evaluated_depsgraph_get(); ev = mesh.evaluated_get(dg); me = ev.to_mesh()
    v = np.array([tuple(ev.matrix_world @ x.co) for x in me.vertices]); ev.to_mesh_clear(); return v

# ---- 座面の高さを決める：座った姿勢で、お尻と腿の一番低い所 ----
names = {g.index: g.name for g in mesh.vertex_groups}
top = np.array([names[max(v.groups, key=lambda g: g.weight).group] if len(v.groups) else '' for v in mesh.data.vertices])
seat_mask = np.isin(top, ['Hips', 'LeftUpLeg', 'RightUpLeg'])
DROP = 0.06
pose(0, None, DROP, 0); bake_to_meshy()
Vp = posed_mesh()
SEAT_Z = float(Vp[seat_mask][:, 2].min())
FOOT_MIN = float(Vp[:, 2].min())
print("SW 座面の高さ %.3f  足の一番低い所 %.3f" % (SEAT_Z, FOOT_MIN))
# 足が地面から 5cm 浮くように、全体（座面ごと）を持ち上げる量
LIFT = max(0.0, 0.05 - FOOT_MIN)
seat_y = float(np.median(Vp[seat_mask][:, 1]))

# 伸びた辺の検査
E = np.array([tuple(e.vertices) for e in mesh.data.edges])
L0 = np.linalg.norm(V0[E[:, 0]] - V0[E[:, 1]], axis=1)
def stretched(Vx):
    L = np.linalg.norm(Vx[E[:, 0]] - Vx[E[:, 1]], axis=1); r = L / np.maximum(L0, 1e-6)
    return int(((r > 2.5) & (L > 0.02)).sum())
print("SW 座った姿勢の伸びた辺", stretched(Vp))

if ROLLTEST:
    sc = bpy.context.scene
    cam_d = bpy.data.cameras.new('cam'); cam_d.type = 'ORTHO'; cam_d.ortho_scale = 0.32
    cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
    sc.render.resolution_x = 360; sc.render.resolution_y = 360
    for o in (rig, meta, arm): o.hide_render = True
    bpy.ops.mesh.primitive_cylinder_add(radius=0.008, depth=1.2, location=(-CHAIN_X, CHAIN_Y, 0.6), vertices=12)
    imgs = []
    for r in (0, 90, 180, 270):
        ROLL_R = r; pose(0, None, DROP, 0); bake_to_meshy()
        hpos = arm.matrix_world @ arm.pose.bones['RightHand'].matrix.translation
        for tag, d in (('f', Vector((-0.25, -1, 0.15))), ('o', Vector((-1, -0.2, 0.1)))):
            d.normalize(); cam.location = hpos + d * 3
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
            fn = os.path.join(OUT, 'parts', 'roll_%03d_%s.png' % (r, tag)); sc.render.filepath = fn
            bpy.ops.render.render(write_still=True); imgs.append(fn)
    import numpy as _np
    ims = [bpy.data.images.load(f) for f in imgs]; w_, h_ = ims[0].size
    buf = _np.ones((h_ * 2, w_ * 4, 4), dtype=_np.float32)
    for k, im in enumerate(ims):
        px = _np.empty(w_ * h_ * 4, dtype=_np.float32); im.pixels.foreach_get(px)
        col, row = k // 2, 1 - (k % 2)
        buf[row * h_:(row + 1) * h_, col * w_:(col + 1) * w_] = px.reshape(h_, w_, 4)
    o_ = bpy.data.images.new('j', w_ * 4, h_ * 2); o_.pixels.foreach_set(buf.ravel())
    o_.filepath_raw = os.path.join(OUT, 'roll_test.png'); o_.file_format = 'PNG'; o_.save()
    print("SW ひねりの試し描き 完了"); sys.exit(0)

# ---- 動きを焼く：座る（静止）と、こぐ（くり返し）----
def bake_clip(name, frames, fn):
    act = bpy.data.actions.new(name); arm.animation_data.action = act
    for f in frames:
        fn(f); bake_to_meshy(f)
    arm.animation_data.action = None
    tr = arm.animation_data.nla_tracks.new(); tr.name = name
    st = tr.strips.new(name, frames[0], act); st.mute = True
    return act
act_sit = bake_clip('Swing_Sit', [0, 1], lambda f: pose(0, None, DROP, 0))
def swing_frame(f):
    ph = 2 * math.pi * f / FR
    th = 0.0 if CLIPS_OUT else SWING * math.sin(ph)   # +で後ろ（骨だけの書き出しでは揺らさない）
    legk = (1 - math.sin(ph)) / 2            # 前へ振るほど伸ばす
    lean = 12 * math.sin(ph)                 # 前へ振るとき上体を後ろへ
    pose(th, legk, DROP, lean)
act_sw = bake_clip('Swing_Pump', list(range(0, FR + 1)), swing_frame)
worst = 0
for f in range(0, FR, 6):
    arm.animation_data.action = act_sw; bpy.context.scene.frame_set(f); upd()
    worst = max(worst, stretched(posed_mesh()))
arm.animation_data.action = None
print("SW こぐ動きの伸びた辺（最大）", worst)

if CLIPS_OUT:
    # 使う側で座面に合わせるための寸法（すべて素のモデルの単位、首の関節の高さも添える）
    arm.animation_data.action = act_sit; bpy.context.scene.frame_set(0); upd()
    lh = arm.matrix_world @ arm.pose.bones['LeftHand'].matrix.translation
    print("SW 寸法 首の高さ %.4f 座面 %.4f 手の左右 %.4f 手の高さ %.4f 手の前後 %.4f 座面の前後 %.4f" % (
        J('neck').z, SEAT_Z, lh.x, lh.z, lh.y, seat_y))
    arm.animation_data.action = None
    for o in bpy.data.objects: o.select_set(o == arm)
    bpy.context.view_layer.objects.active = arm
    for tr in arm.animation_data.nla_tracks:   # 書き出す前に、トラックとストリップの消音を両方解く（ストリップが消音のままだと中身が素の姿勢になる）
        tr.mute = False
        for st_ in tr.strips: st_.mute = False
    bpy.ops.export_scene.gltf(filepath=CLIPS_OUT, export_format='GLB', use_selection=True,
                              export_animations=True, export_animation_mode='NLA_TRACKS',
                              export_skins=False, export_yup=True)
    print("SW 骨だけの動きを書き出した", CLIPS_OUT, os.path.getsize(CLIPS_OUT))
    sys.exit(0)

# 全体を持ち上げる（座面・鎖と一緒に）
arm.location.z += LIFT
SEAT_Z += LIFT; BARZ = BAR_Z + LIFT

# ---- ブランコ ----
def mat(name, rgb, rough=0.6, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.diffuse_color = (*rgb, 1)
    return m
wood, steel, frame_c = mat('wood', (0.55, 0.33, 0.16)), mat('chain', (0.62, 0.64, 0.68), 0.35, 1.0), mat('frame', (0.20, 0.45, 0.80))
piv = bpy.data.objects.new('SwingPivot', None); bpy.context.scene.collection.objects.link(piv)
piv.location = (0, CHAIN_Y, BARZ)
def add_cube(name, size, loc, m, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object
    o.name = name; o.scale = size; o.data.materials.append(m)
    if parent: o.parent = parent; o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o
def add_cyl(name, r, p0, p1, m, parent=None):
    p0, p1 = Vector(p0), Vector(p1); d = p1 - p0
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=(p0 + p1) / 2, vertices=12)
    o = bpy.context.active_object; o.name = name
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); o.data.materials.append(m)
    if parent: o.parent = parent; o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o
bpy.context.view_layer.update()
seat_w = CHAIN_X * 2 + 0.06
add_cube('Seat', (seat_w, 0.17, 0.025), (0, seat_y, SEAT_Z - 0.0125), wood, piv)
for sx in (1, -1):
    add_cyl('Chain', 0.008, (sx * CHAIN_X, CHAIN_Y, SEAT_Z), (sx * CHAIN_X, CHAIN_Y, BARZ), steel, piv)
    for sy in (1, -1):   # A字の柱
        add_cyl('Post', 0.03, (sx * (CHAIN_X + 0.35), CHAIN_Y + sy * 0.45, 0), (sx * (CHAIN_X + 0.35), CHAIN_Y, BARZ + 0.03), frame_c)
add_cyl('Bar', 0.035, (-(CHAIN_X + 0.40), CHAIN_Y, BARZ + 0.03), (CHAIN_X + 0.40, CHAIN_Y, BARZ + 0.03), frame_c)
add_cube('Ground', (3, 3, 0.01), (0, 0, -0.005), mat('ground', (0.80, 0.78, 0.72)))
# 支点の回転をこぐ動きに合わせる
piv.animation_data_create()
pact = bpy.data.actions.new('SwingPivotAct'); piv.animation_data.action = pact
for f in range(0, FR + 1):
    piv.rotation_euler = (math.radians(SWING * math.sin(2 * math.pi * f / FR)), 0, 0)
    piv.keyframe_insert('rotation_euler', frame=f)

# ---- 描く ----
sc = bpy.context.scene
cam_d = bpy.data.cameras.new('cam'); cam_d.type = 'ORTHO'
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.display.shading.show_shadows = True
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('w'); sc.world = w; w.color = (1, 1, 1)
sc.render.resolution_x = 520; sc.render.resolution_y = 600
for o in (rig, meta): o.hide_render = True
arm.hide_render = True
def shoot(path, center, width, az, el):
    cam_d.ortho_scale = width
    d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
    cam.location = Vector(center) + d * 6
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)
def join(files, outp):
    imgs = [bpy.data.images.load(f) for f in files]
    w_, h_ = imgs[0].size
    buf = np.ones((h_, w_ * len(imgs), 4), dtype=np.float32)
    for k, im in enumerate(imgs):
        px = np.empty(w_ * h_ * 4, dtype=np.float32); im.pixels.foreach_get(px)
        buf[:, k * w_:(k + 1) * w_] = px.reshape(h_, w_, 4)
    o_ = bpy.data.images.new('joined', w_ * len(imgs), h_, alpha=True)
    o_.pixels.foreach_set(buf.ravel()); o_.filepath_raw = outp; o_.file_format = 'PNG'; o_.save()
C = (0, CHAIN_Y, (BARZ + 0.0) / 2 + 0.05)
# 座った姿勢（揺れなし）
arm.animation_data.action = act_sit; piv.animation_data.action = None; piv.rotation_euler = (0, 0, 0)
sc.frame_set(0); upd()
files = []
for tag, az, el in (('front', 0, 5), ('side', 90, 5), ('game', 45, 30)):
    fn = os.path.join(OUT, 'parts', 'sit_%s.png' % tag); files.append(fn)
    shoot(fn, C, 1.95, az, el)
join(files, os.path.join(OUT, 'swing_sit.png'))
# 顔まわりに寄った絵（手と鎖）
sc.render.resolution_x = 700; sc.render.resolution_y = 520
shoot(os.path.join(OUT, 'swing_sit_close.png'), (0, CHAIN_Y, SEAT_Z + 0.25), 0.95, 25, 12)
# こぐ動き：横から4コマ
sc.render.resolution_x = 520; sc.render.resolution_y = 600
arm.animation_data.action = act_sw; piv.animation_data.action = pact
for o in bpy.data.objects:   # 横からの絵では手前の柱が体に重なるので、柱と横棒は描かない
    if o.name.startswith(('Post', 'Bar')): o.hide_render = True
files = []
for k, f in enumerate((0, 12, 24, 36)):
    sc.frame_set(f); upd()
    fn = os.path.join(OUT, 'parts', 'pump_%02d.png' % f); files.append(fn)
    shoot(fn, (0, CHAIN_Y, 0.95), 2.3, 90, 3)
join(files, os.path.join(OUT, 'swing_pump.png'))

# ---- 書き出し：今のモデルに2本の動きを足した glb（元の動きも入れる）----
arm.location.z -= LIFT
arm.animation_data.action = None
for x in old_acts:
    tr = arm.animation_data.nla_tracks.new(); tr.name = x.name
    s_ = tr.strips.new(x.name, int(x.frame_range[0]), x); s_.mute = True
for tr in arm.animation_data.nla_tracks:   # 書き出す前に消音を解く
    tr.mute = False
    for st_ in tr.strips: st_.mute = False
for o in bpy.data.objects: o.select_set(o in (arm, mesh))
bpy.context.view_layer.objects.active = arm
glb = os.path.join(OUT, 'girl_v55_swing.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True,
                          export_animations=True, export_animation_mode='NLA_TRACKS',
                          export_skins=True, export_yup=True)
arm.location.z += LIFT
for o in (arm, rig, meta): o.hide_set(True); o.hide_viewport = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'swing_test.blend'))
print("SW 保存", OUT)
