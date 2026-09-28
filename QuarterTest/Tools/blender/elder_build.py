# -*- coding: utf-8 -*-
"""公園のベンチに座るお爺ちゃん・お婆ちゃんを、Higgsfield を使わず Blender の単純な形だけで組む。
   ・形は球・円柱などの組み合わせ（公園の遊具と同じローポリ調）。色は材質の無地だけ。
   ・骨は自前の簡単な骨組み。部品ごとに1本の骨へ付ける（服の胴やスカートは高さで2本に分ける）。
   ・寸法は公園の世界の単位そのまま（倍率1）。足元が原点、前は -Y。
     ベンチの座面は高さ0.64なので、座って足が地面に着くよう脚を長めにしてある（膝0.62・腰1.02）。
   ・動かない置物。骨は座る姿勢を作るためだけに使い、書き出す前に形へ焼き込んで外す（骨なしの glb）。
   ・シンボルエンカウント（話しかけると特別な演出）の相手として公園のベンチに置く。
   実行: blender -b --factory-startup -P elder_build.py -- 出力フォルダ
   出力: elder_grandma.glb / elder_grandpa.glb と、確かめ用の絵 check_grandma.png / check_grandpa.png"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector, Matrix, Quaternion

a = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(a[0])
os.makedirs(os.path.join(OUT, 'parts'), exist_ok=True)

# ---- 骨組みの寸法（立ち姿）----
ANKLE, KNEE, HIP = 0.07, 0.62, 1.02
CHEST, SHOULDER, NECK, HEAD_C = 1.30, 1.46, 1.52, 1.82
LEG_X, ARM_X = 0.11, 0.24
SEAT = 0.64                      # ベンチの座面の高さ
SIT_HIP = 0.74                   # 座ったときの股関節の高さ（腿の太さ0.09ぶん座面より上）

SKIN = (1.0, 0.82, 0.70); CHEEK = (0.96, 0.62, 0.62); DARK = (0.18, 0.14, 0.13)

def lin(c):   # 色の数字は見た目の色（sRGB）で書いてある。材質へは直線の値で渡す（渡さないと公園で白っぽく飛んだ）
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def mat(name, rgb):
    m = bpy.data.materials.get(name)
    if m: return m
    rgb = tuple(lin(c) for c in rgb)
    m = bpy.data.materials.new(name); m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = 0.8
    return m

PARTS = []      # (物, 重みの決め方)
def keep(o, rgb, bones):
    o.data.materials.append(mat('m_%.2f_%.2f_%.2f' % rgb, rgb))
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.shade_smooth()
    PARTS.append((o, bones)); return o
def sphere(c, r, rgb, bones, scale=(1, 1, 1), seg=24, ring=16):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=c, segments=seg, ring_count=ring)
    o = bpy.context.active_object; o.scale = scale; return keep(o, rgb, bones)
def tube(p, q, r, rgb, bones, r2=None, seg=16):
    p, q = Vector(p), Vector(q); d = q - p
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=(p + q) / 2, vertices=seg)
    else:
        bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=d.length, location=(p + q) / 2, vertices=seg)
    o = bpy.context.active_object
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = d.normalized().to_track_quat('Z', 'Y')
    return keep(o, rgb, bones)
def torus(c, R, r, rgb, bones, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=c, rotation=rot, major_segments=24, minor_segments=8)
    return keep(bpy.context.active_object, rgb, bones)
def box(c, s, rgb, bones, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=c, rotation=rot)
    o = bpy.context.active_object; o.scale = s; return keep(o, rgb, bones)
def cut(o, drop):
    """drop(world座標) が真の頂点を消す（髪の前を開けるなど）"""
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if drop(v.co)], context='VERTS')
    bm.to_mesh(o.data); bm.free()

def ss(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t)
# 胴は腰と胸の間で重みを分ける
def torso_w(co): w = ss(1.10, 1.32, co.z); return {'chest': w, 'hips': 1 - w}
# スカート・ズボンの上は、下へ行くほど腿の骨へ。左右は x の符号で分ける
def skirt_w(co):
    w = ss(0.98, 0.84, co.z); side = 'thigh.L' if co.x >= 0 else 'thigh.R'
    return {side: w, 'hips': 1 - w}

# ---- 共通の体 ----
def body(cloth, sleeve, legc, shoe, skirt=None):
    # 頭
    sphere((0, 0, HEAD_C), 0.28, SKIN, 'head', seg=32, ring=20)
    sphere((0, -0.275, HEAD_C - 0.04), 0.045, SKIN, 'head')                         # 鼻
    for s in (1, -1):
        sphere((s * 0.28, 0.0, HEAD_C - 0.02), 0.06, SKIN, 'head', scale=(0.6, 1, 1))  # 耳
        sphere((s * 0.165, -0.225, HEAD_C - 0.07), 0.05, CHEEK, 'head', scale=(1, 0.3, 0.6))   # 頬の赤み
    # 首・胴
    tube((0, 0.0, NECK - 0.06), (0, 0.0, NECK + 0.08), 0.08, SKIN, 'chest')
    sphere((0, 0.0, 1.24), 1.0, cloth, torso_w, scale=(0.23, 0.18, 0.30))
    # 腕（肩の丸み・上腕・ひじ・前腕・手）
    for S, s in (('L', 1), ('R', -1)):
        sh, el, wr = (s * ARM_X, 0, SHOULDER), (s * 0.30, 0, 1.18), (s * 0.33, 0, 0.94)
        sphere(sh, 0.075, sleeve, 'upper_arm.' + S)
        tube(sh, el, 0.068, sleeve, 'upper_arm.' + S)
        sphere(el, 0.064, sleeve, 'forearm.' + S)
        tube(el, wr, 0.062, sleeve, 'forearm.' + S, r2=0.054)
        sphere((s * 0.335, 0, 0.90), 0.062, SKIN, 'hand.' + S, scale=(0.9, 1, 1.15))
    # 脚（腿・膝・すね・靴）
    for S, s in (('L', 1), ('R', -1)):
        hp, kn, an = (s * LEG_X, 0, HIP), (s * LEG_X, 0, KNEE), (s * LEG_X, 0, ANKLE)
        tube(hp, kn, 0.095, legc, 'thigh.' + S, r2=0.085)
        sphere(kn, 0.085, legc, 'shin.' + S)
        tube(kn, an, 0.082, legc, 'shin.' + S, r2=0.07)
        sphere((s * LEG_X, -0.05, 0.05), 1.0, shoe, 'foot.' + S, scale=(0.085, 0.15, 0.06))
    # 腰まわり
    if skirt:
        tube((0, 0, 1.06), (0, 0, 0.66), 0.215, skirt, skirt_w, r2=0.27, seg=24)
    else:
        sphere((0, 0, 1.02), 1.0, legc, skirt_w, scale=(0.22, 0.17, 0.14))

def grandma():
    HAIR = (0.80, 0.80, 0.83); CARD = (0.72, 0.62, 0.84); BLOUSE = (0.97, 0.95, 0.90)
    body(CARD, CARD, (0.62, 0.55, 0.50), (0.40, 0.28, 0.22), skirt=(0.36, 0.30, 0.42))
    # 髪：頭の上と後ろを覆い、顔の前は開ける。お団子を後ろ上に
    h = sphere((0, 0.02, HEAD_C + 0.02), 0.30, HAIR, 'head', seg=32, ring=20)
    cut(h, lambda v: (v.y < -0.06 and v.z < HEAD_C + 0.10) or v.z < HEAD_C - 0.14)
    sphere((0, 0.14, HEAD_C + 0.26), 0.12, HAIR, 'head')
    torus((0, 0.10, HEAD_C + 0.20), 0.07, 0.02, (0.55, 0.40, 0.70), 'head', rot=(math.radians(60), 0, 0))   # 髪留め
    # 目（にっこり閉じた目）と丸眼鏡
    for s in (1, -1):
        sphere((s * 0.10, -0.268, HEAD_C + 0.02), 0.03, DARK, 'head', scale=(1.2, 0.35, 0.35))
        torus((s * 0.10, -0.285, HEAD_C + 0.02), 0.058, 0.008, (0.55, 0.45, 0.30), 'head', rot=(math.radians(90), 0, 0))
    box((0, -0.29, HEAD_C + 0.03), (0.05, 0.012, 0.012), (0.55, 0.45, 0.30), 'head')
    sphere((0, -0.262, HEAD_C - 0.12), 0.03, (0.75, 0.40, 0.40), 'head', scale=(1.3, 0.3, 0.45))   # 口
    # カーディガンの前あき（ブラウス）とボタン
    box((0, -0.168, 1.30), (0.07, 0.02, 0.26), BLOUSE, 'chest')
    for z in (1.36, 1.26, 1.16):
        sphere((0.05, -0.18, z), 0.018, (0.95, 0.92, 0.85), torso_w)

def grandpa():
    HAIR = (0.93, 0.93, 0.91); SWEAT = (0.45, 0.55, 0.40); SHIRT = (0.90, 0.92, 0.95); CAP = (0.76, 0.66, 0.50)
    body(SWEAT, SWEAT, (0.42, 0.42, 0.46), (0.30, 0.22, 0.18))
    # 横と後ろだけの白髪
    h = sphere((0, 0.02, HEAD_C), 0.295, HAIR, 'head', seg=32, ring=20)
    cut(h, lambda v: v.y < -0.02 or v.z > HEAD_C + 0.10 or v.z < HEAD_C - 0.16)
    # ハンチング帽
    sphere((0, 0.01, HEAD_C + 0.13), 1.0, CAP, 'head', scale=(0.30, 0.31, 0.12))
    box((0, -0.30, HEAD_C + 0.10), (0.26, 0.10, 0.018), CAP, 'head', rot=(math.radians(-12), 0, 0))
    # 目・白い眉・口ひげ
    for s in (1, -1):
        sphere((s * 0.10, -0.268, HEAD_C + 0.01), 0.022, DARK, 'head', scale=(1.0, 0.4, 1.0))
        sphere((s * 0.10, -0.262, HEAD_C + 0.07), 0.04, HAIR, 'head', scale=(1.3, 0.4, 0.45))
        sphere((s * 0.05, -0.285, HEAD_C - 0.09), 0.05, HAIR, 'head', scale=(1.2, 0.5, 0.55))
    # シャツの襟もと（胸の真ん中に置くとポケットに見えたので、首もとへ）
    box((0, -0.115, 1.47), (0.10, 0.03, 0.07), SHIRT, 'chest', rot=(math.radians(-35), 0, 0))

# ---- 骨組み ----
BONES = [  # 名前, 頭, 尾, 親
    ('root', (0, 0, 0), (0, 0, 0.2), None),
    ('hips', (0, 0, HIP), (0, 0, 1.18), 'root'),
    ('chest', (0, 0, 1.18), (0, 0, NECK), 'hips'),
    ('head', (0, 0, NECK), (0, 0, 2.10), 'chest'),
]
for S, s in (('L', 1), ('R', -1)):
    BONES += [('upper_arm.' + S, (s * ARM_X, 0, SHOULDER), (s * 0.30, 0, 1.18), 'chest'),
              ('forearm.' + S, (s * 0.30, 0, 1.18), (s * 0.33, 0, 0.94), 'upper_arm.' + S),
              ('hand.' + S, (s * 0.33, 0, 0.94), (s * 0.34, 0, 0.84), 'forearm.' + S),
              ('thigh.' + S, (s * LEG_X, 0, HIP), (s * LEG_X, 0, KNEE), 'hips'),
              ('shin.' + S, (s * LEG_X, 0, KNEE), (s * LEG_X, 0, ANKLE), 'thigh.' + S),
              ('foot.' + S, (s * LEG_X, 0, ANKLE), (s * LEG_X, -0.15, 0.03), 'shin.' + S)]
UPPER, FORE = (Vector((0.30, 0, 1.18)) - Vector((ARM_X, 0, SHOULDER))).length, (Vector((0.33, 0, 0.94)) - Vector((0.30, 0, 1.18))).length

def build(kind):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    PARTS.clear()
    (grandma if kind == 'grandma' else grandpa)()
    cane = None
    if kind == 'grandpa':   # 杖：座ったときの両ひざの間に立てる（root に付けるので、座る姿勢のときの場所に置く）
        cane = [tube((0, -0.62, 0.0), (0, -0.62, 0.78), 0.022, (0.42, 0.28, 0.16), 'root'),
                sphere((0, -0.62, 0.79), 0.04, (0.42, 0.28, 0.16), 'root', scale=(1.6, 1, 0.8))]
    # 骨
    arm_d = bpy.data.armatures.new(kind + '_arm'); arm = bpy.data.objects.new(kind + '_rig', arm_d)
    bpy.context.scene.collection.objects.link(arm); bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for n, h, t, p in BONES:
        b = arm_d.edit_bones.new(n); b.head = h; b.tail = t
        if p: b.parent = arm_d.edit_bones[p]
    bpy.ops.armature.select_all(action='SELECT'); bpy.ops.armature.calculate_roll(type='GLOBAL_NEG_Y')
    bpy.ops.object.mode_set(mode='OBJECT')
    # 重みを付けてからひとつにまとめる
    names = [n for n, *_ in BONES]
    for o, rule in PARTS:
        for n in names: o.vertex_groups.new(name=n)
        for v in o.data.vertices:
            ws = {rule: 1.0} if isinstance(rule, str) else rule(v.co)
            for n, w in ws.items():
                if w > 1e-4: o.vertex_groups[n].add([v.index], w, 'REPLACE')
    bpy.ops.object.select_all(action='DESELECT')
    for o, _ in PARTS: o.select_set(True)
    body_o = PARTS[0][0]; bpy.context.view_layer.objects.active = body_o
    bpy.ops.object.join(); body_o.name = kind
    body_o.parent = arm
    md = body_o.modifiers.new('arm', 'ARMATURE'); md.object = arm
    return arm, body_o

# ---- 姿勢 ----
def pose_sit(arm, kind):
    P = arm.pose.bones
    upd = bpy.context.view_layer.update
    for pb in P:
        pb.rotation_mode = 'QUATERNION'; pb.matrix_basis = Matrix.Identity(4)
    upd()
    W = arm.matrix_world
    def setw(pb, loc, rot):
        pb.matrix = W.inverted() @ Matrix.LocRotScale(loc, rot, Vector((1, 1, 1))); upd()
    def aim(n, d):
        pb = P[n]; loc, rot, _ = (W @ pb.matrix).decompose()
        cur = (rot @ Vector((0, 1, 0))).normalized()
        setw(pb, loc, cur.rotation_difference(Vector(d).normalized()) @ rot)
    def head_of(n): return (W @ P[n].matrix).translation.copy()
    lean = 14 if kind == 'grandma' else 5
    # 腰を下げ、上体を少し前へ
    loc, rot, _ = (W @ P['hips'].matrix).decompose()
    setw(P['hips'], Vector((0, 0, SIT_HIP)), Quaternion((1, 0, 0), math.radians(lean * 0.3)) @ rot)
    loc, rot, _ = (W @ P['chest'].matrix).decompose()
    setw(P['chest'], loc, Quaternion((1, 0, 0), math.radians(lean * 0.7)) @ rot)
    loc, rot, _ = (W @ P['head'].matrix).decompose()
    setw(P['head'], loc, Quaternion((1, 0, 0), math.radians(-lean * 0.8)) @ rot)
    # 脚：腿は前（少し下がる）、すねは下、足は前
    for S, s in (('L', 1), ('R', -1)):
        hp = head_of('thigh.' + S)
        kn = hp + Vector((s * 0.01, -0.39, SEAT - SIT_HIP + 0.0))
        aim('thigh.' + S, kn - hp)
        kn = head_of('shin.' + S)
        an = Vector((kn.x, kn.y - 0.03, ANKLE))
        aim('shin.' + S, an - kn)
        aim('foot.' + S, (0, -1, -0.2))
    # 腕：お婆ちゃんは膝の上で手を重ねる、お爺ちゃんは杖の頭に両手
    for S, s in (('L', 1), ('R', -1)):
        sh = head_of('upper_arm.' + S)
        if kind == 'grandma':
            tgt = Vector((s * 0.05, -0.30, SIT_HIP + 0.12))
        else:
            tgt = Vector((s * 0.035, -0.62, 0.86))
        # 2本の骨の IK（ひじは外・後ろへ）
        d = tgt - sh; L = min(d.length, UPPER + FORE - 1e-3)
        dn = d.normalized()
        cosA = (UPPER ** 2 + L ** 2 - FORE ** 2) / (2 * UPPER * L)
        pole = Vector((s * 1.0, 0.6, -0.2))
        side = (pole - dn * pole.dot(dn)).normalized()
        el = sh + dn * UPPER * cosA + side * UPPER * math.sqrt(max(0.0, 1 - cosA ** 2))
        aim('upper_arm.' + S, el - sh)
        aim('forearm.' + S, (sh + dn * L) - head_of('forearm.' + S))
        aim('hand.' + S, (0, -0.4, -1) if kind == 'grandpa' else (-s * 0.6, -0.8, -0.3))

def key_all(arm, f):
    for pb in arm.pose.bones:
        pb.keyframe_insert('rotation_quaternion', frame=f, group=pb.name)
        pb.keyframe_insert('location', frame=f, group=pb.name)

def clips(arm, kind):
    if arm.animation_data is None: arm.animation_data_create()
    made = []
    def clip(name, frames, fn):
        act = bpy.data.actions.new(name); arm.animation_data.action = act
        for f in frames: fn(f); key_all(arm, f)
        arm.animation_data.action = None
        tr = arm.animation_data.nla_tracks.new(); tr.name = name
        tr.strips.new(name, frames[0], act); made.append((name, act, frames))
    clip('Sit', [0, 1], lambda f: pose_sit(arm, kind))
    return made

# ---- 絵 ----
def render_checks(kind, arm, body_o, made):
    sc = bpy.context.scene
    cam_d = bpy.data.cameras.new('cam'); cam_d.type = 'ORTHO'
    cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
    sc.display.shading.show_shadows = True
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('w'); sc.world = w; w.color = (1, 1, 1)
    sc.render.resolution_x = 300; sc.render.resolution_y = 420
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
    gm = mat('ground', (0.80, 0.78, 0.72)); bpy.context.active_object.data.materials.append(gm)
    # ベンチ（park12.py と同じ寸法。座る人の腰が座面の後ろ寄りに来る位置）
    bench = []
    wood = mat('wood', (0.62, 0.42, 0.25))
    for c, s in (((0, 0.075, SEAT - 0.04), (1.3, 0.6, 0.08)), ((0, 0.075 + 0.28, 0.95), (1.3, 0.07, 0.4)),
                 ((0.55, 0.075, 0.28), (0.08, 0.56, 0.56)), ((-0.55, 0.075, 0.28), (0.08, 0.56, 0.56))):
        bpy.ops.mesh.primitive_cube_add(size=1, location=c); o = bpy.context.active_object; o.scale = s
        o.data.materials.append(wood); bench.append(o)
    arm.hide_render = True
    def shoot(path, center, width, az, el):
        cam_d.ortho_scale = width
        d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                    -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
        cam.location = Vector(center) + d * 8
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    files = []
    # 立ち姿（ベンチは隠す）
    arm.animation_data.action = None
    for tr in arm.animation_data.nla_tracks: tr.mute = True
    for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for o in bench: o.hide_render = True
    for az in (0, 90, 30):
        fn = os.path.join(OUT, 'parts', '%s_stand_%d.png' % (kind, az)); files.append(fn)
        shoot(fn, (0, 0, 1.05), 2.5, az, 8)
    # 座り姿
    for o in bench: o.hide_render = False
    arm.animation_data.action = made[0][1]; sc.frame_set(0)
    for az in (0, 90, 30):
        fn = os.path.join(OUT, 'parts', '%s_sit_%d.png' % (kind, az)); files.append(fn)
        shoot(fn, (0, 0, 1.05), 2.5, az, 8)
    arm.animation_data.action = None
    imgs = [bpy.data.images.load(f) for f in files]
    w_, h_ = imgs[0].size; cols, rows = 3, 2
    buf = np.ones((h_ * rows, w_ * cols, 4), dtype=np.float32)
    for k, im in enumerate(imgs):
        px = np.empty(w_ * h_ * 4, dtype=np.float32); im.pixels.foreach_get(px)
        r_, c_ = rows - 1 - k // cols, k % cols
        buf[r_ * h_:(r_ + 1) * h_, c_ * w_:(c_ + 1) * w_] = px.reshape(h_, w_, 4)
    o_ = bpy.data.images.new('j', w_ * cols, h_ * rows); o_.pixels.foreach_set(buf.ravel())
    o_.filepath_raw = os.path.join(OUT, 'check_%s.png' % kind); o_.file_format = 'PNG'; o_.save()
    for o in bench: bpy.data.objects.remove(o, do_unlink=True)

def export(kind, arm, body_o, made):
    # 座る姿勢を形に焼き込み、骨を外して、動かない置物として書き出す
    arm.animation_data.action = made[0][1]; bpy.context.scene.frame_set(0); bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    body_o.select_set(True); bpy.context.view_layer.objects.active = body_o
    bpy.ops.object.modifier_apply(modifier='arm')
    # 座面より下へ入り込んだ所（スカートの後ろ・お尻）を座面の上へ押し上げる。すね・靴・杖は座面より前なので対象外
    nfix = 0
    for v in body_o.data.vertices:
        if v.co.y > -0.22 and v.co.z < SEAT + 0.005:
            v.co.z = SEAT + 0.005; nfix += 1
    print('EB %s 座面へ押し上げた頂点 %d' % (kind, nfix))
    mw = body_o.matrix_world.copy(); body_o.parent = None; body_o.matrix_world = mw
    body_o.vertex_groups.clear()
    bpy.data.objects.remove(arm, do_unlink=True)
    path = os.path.join(OUT, 'elder_%s.glb' % kind)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                              export_animations=False, export_skins=False, export_yup=True)
    V = np.array([tuple(body_o.matrix_world @ v.co) for v in body_o.data.vertices])
    print("EB %s: 頂点 %d 高さ %.3f 前後 %.3f〜%.3f 書き出し %s %d" % (kind, len(V), V[:, 2].max(), V[:, 1].min(), V[:, 1].max(), path, os.path.getsize(path)))

for kind in ('grandma', 'grandpa'):
    arm, body_o = build(kind)
    made = clips(arm, kind)
    # 座ったときの足の低さ・お尻の低さ
    arm.animation_data.action = made[0][1]; bpy.context.scene.frame_set(0); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); ev = body_o.evaluated_get(dg); me = ev.to_mesh()
    Vs = np.array([tuple(ev.matrix_world @ v.co) for v in me.vertices]); ev.to_mesh_clear()
    back = Vs[(Vs[:, 1] > -0.05)]
    print("EB %s 座り: 一番低い所 %.3f / 腰より後ろの一番低い所 %.3f（座面 %.2f）/ 一番後ろ y=%.3f" % (kind, Vs[:, 2].min(), back[:, 2].min(), SEAT, Vs[:, 1].max()))
    arm.animation_data.action = None
    render_checks(kind, arm, body_o, made)
    export(kind, arm, body_o, made)
