# -*- coding: utf-8 -*-
"""髪の房の中にある「絵だけ明るい小さな島」（Meshy が絵の切れ目で切り離し、絵の端の明るい色を割り当てた 1〜数面の島）に、
   となりの髪の面の絵の位置（UV）を貼り直して、髪の色にする。形・骨・重み・動きはそのまま、UV だけ。
   お嬢様（小学生編）は、目の横の顔の前にかかる房のふちに、肌色の細い筋が何度直しても残った。
   正体は 1〜2 面だけの島で、絵の位置が絵の端（u≈0.998・0.005）にあり、そこが明るい色だった。
   hairskinpaint.py は「半分以上が暗い島」だけを塗り、islandpaint.py・hairpad.py も島の中や島のすき間しか見ないので、毎回漏れた。
   1) 島（頂点のつながり）のうち、面が MAXF 以下で、明るい面（明るさ ≥ 0.45・彩度 < 0.4・青系でない）が半分以上のもの
   2) その島の面と同じ位置の頂点を持つ、ほかの島の面（となり）を数え、暗い面（明るさ < 0.4）が DFR 以上なら「髪なのに明るい島」
   3) 島の面ごとに、一番近い暗いとなりの面の UV の真ん中の 1 点を、すべての角に貼る（その面と同じ無地の髪の色になる）
   顔の正面（|x| < 0.075・y < −0.11・0.88 < 高さ < 1.0）は外す（目の光・白目のまわりに暗いまつげ・黒目がとなりにある）
   --check で、直す面を赤にして頭を何方向からも描く（UV は変えない・glb も書かない）。**直す前に必ず描いて見る**
   実行: blender -b --factory-startup -P orphanfix.py -- 入力.glb 出力.glb [--maxf 8] [--dfr 0.6] [--check 絵.png]"""
import bpy, bmesh, sys, math, os, colorsys, collections, numpy as np
from mathutils import Vector, Matrix
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
MAXF = int(opt('--maxf', 8)); DFR = float(opt('--dfr', 0.6)); CHECK = opt('--check', None)
# --float DIST：島でなく面ごとに、「肌の前に浮いている明るい面」も直す。前髪の先の裏（下を向いた面）や目の横の房の内側に明るい絵が
#   貼られていて、右前から見ると前髪のすき間が白っぽく見えた（「反対の角度だって酷い」）。これらの面は、顔の肌と同じ島に入っていて
#   （島 47 面に右目も入っていた）、島ごとに塗ると目まで黒くなる。面の真ん中から頭のうしろ（+y）へ光線を飛ばし、DIST 以内に
#   前を向いた明るい面（肌）があれば「肌の前に浮いている」＝髪。額・目・ほおの面は、うしろに別の肌がないので入らない
FLOAT = float(opt('--float', 0)) if '--float' in a else 0.0
# --sheet THICK：面の裏側（面の向きと反対）へ光線を飛ばし、THICK 以内に反対向きの面があれば「薄い板＝髪の房」とみなして直す。
#   目の横の房のふちは表の面も 2mm うしろの裏の面も明るい絵で、--float では裏の面を肌と取り違えて漏れた。頭や顔は厚みがあるので入らない
SHEET = float(opt('--sheet', 0)) if '--sheet' in a else 0.0
SRC, OUT = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data; MW = me.matrix_world
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
bm = bmesh.new(); bm.from_mesh(m); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table(); uvL = bm.loops.layers.uv.active
# 島（頂点のつながり）
par = list(range(len(bm.verts)))
def find(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
for e in bm.edges:
    ra, rb = find(e.verts[0].index), find(e.verts[1].index)
    if ra != rb: par[ra] = rb
def fuv(f): return sum((l[uvL].uv for l in f.loops), Vector((0, 0))) / len(f.loops)
def cls(f):
    uv = fuv(f); h, s, v = colorsys.rgb_to_hsv(*px[int(np.clip(uv.y, 0, .9999) * H_), int(np.clip(uv.x, 0, .9999) * W_), :3])
    return 'D' if v < 0.4 else ('L' if (v >= 0.45 and s < 0.4 and not (0.5 <= h <= 0.8 and s >= 0.1)) else 'O')
K = {f.index: cls(f) for f in bm.faces}
isl = collections.defaultdict(list)
for f in bm.faces: isl[find(f.verts[0].index)].append(f)
# 同じ位置の頂点 → 面
def key(v): return tuple(round(x, 5) for x in v.co)
posf = collections.defaultdict(set)
for f in bm.faces:
    for v in f.verts: posf[key(v)].add(f.index)
def face_front(c): return abs(c.x) < 0.075 and c.y < -0.11 and 0.88 < c.z < 1.0
fix = {}   # 面 → 貼る UV
nisl = 0
for r, fs in isl.items():
    if len(fs) > MAXF: continue
    if sum(1 for f in fs if K[f.index] == 'L') * 2 < len(fs): continue
    ids = {f.index for f in fs}
    nb = set()
    for f in fs:
        for v in f.verts: nb |= posf[key(v)]
    nb -= ids
    if not nb: continue
    dk = [bm.faces[i] for i in nb if K[i] == 'D']
    if len(dk) / len(nb) < DFR: continue
    cen = MW @ (sum((f.calc_center_median() for f in fs), Vector()) / len(fs))
    if cen.z < 0.85 or face_front(cen): continue
    nisl += 1
    for f in fs:
        c = f.calc_center_median(); g = min(dk, key=lambda d: (d.calc_center_median() - c).length)
        fix[f.index] = fuv(g).copy()
print("OF 髪なのに明るい小さな島 %d・面 %d" % (nisl, len(fix)))
if FLOAT > 0:
    from mathutils.bvhtree import BVHTree
    bw = bm.copy(); bw.transform(MW); bw.faces.ensure_lookup_table(); tree = BVHTree.FromBMesh(bw)
    N3 = MW.to_3x3().inverted().transposed()
    darkf = [f for f in bm.faces if K[f.index] == 'D']
    from mathutils.kdtree import KDTree
    kd = KDTree(len(darkf))
    for i, f in enumerate(darkf): kd.insert(MW @ f.calc_center_median(), i)
    kd.balance()
    nf = 0
    for f in bm.faces:
        if f.index in fix or K[f.index] != 'L': continue
        c = MW @ f.calc_center_median()
        if c.z < 0.88: continue
        h = tree.ray_cast(c + Vector((0, 0.0005, 0)), Vector((0, 1, 0)), FLOAT)
        if h[0] is None or h[2] == f.index: continue
        if K[h[2]] != 'L' or (N3 @ bm.faces[h[2]].normal).normalized().y > -0.3: continue   # うしろにあるのが前向きの肌
        # 一番近い暗い面（髪）の UV を貼る
        co, i, d = kd.find(c)
        if d > 0.03: continue
        fix[f.index] = fuv(darkf[i]).copy(); nf += 1
    bw.free()
    print("OF 肌の前に浮いている明るい面 %d（合計 %d）" % (nf, len(fix)))
if SHEET > 0:
    from mathutils.bvhtree import BVHTree
    from mathutils.kdtree import KDTree
    bw = bm.copy(); bw.transform(MW); bw.faces.ensure_lookup_table(); tree = BVHTree.FromBMesh(bw)
    darkf = [f for f in bm.faces if K[f.index] == 'D']
    kd = KDTree(len(darkf))
    for i, f in enumerate(darkf): kd.insert(MW @ f.calc_center_median(), i)
    kd.balance()
    ns = 0
    for f in bw.faces:
        if f.index in fix or K[f.index] != 'L': continue
        c = f.calc_center_median()
        if c.z < 0.9: continue
        n = f.normal.normalized()
        h = tree.ray_cast(c - n * 0.0003, -n, SHEET)
        if h[0] is None or h[2] == f.index: continue
        if bw.faces[h[2]].normal.normalized().dot(n) > -0.5: continue   # 反対向きの面（板の裏）
        co, i, d = kd.find(c)
        if d > 0.03: continue
        fix[f.index] = fuv(darkf[i]).copy(); ns += 1
    bw.free()
    print("OF 薄い板（髪の房）の明るい面 %d（合計 %d）" % (ns, len(fix)))
if CHECK:
    red = bpy.data.materials.new("red"); red.diffuse_color = (1, 0, 0, 1); m.materials.append(red); ri = len(m.materials) - 1
    for fi in fix: bm.faces[fi].material_index = ri
    bm.to_mesh(m); bm.free()
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
    if arm.animation_data:
        for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
        arm.animation_data.action = None
    for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_backface_culling = False; sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = False; sc.world.color = (1, 1, 1)
    CW = 400; sc.render.resolution_x = CW; sc.render.resolution_y = CW
    cd = bpy.data.cameras.new("c"); cd.type = 'ORTHO'; cd.ortho_scale = 0.34; cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
    C = Vector((0, -0.01, 0.97)); tiles = []; tmp = os.path.join(os.path.dirname(CHECK), "_of"); os.makedirs(tmp, exist_ok=True)
    for az, el in ((0, 0), (40, 0), (90, 0), (180, 0), (-90, 0), (-40, 0), (0, -35), (0, 45)):
        ar_, el_ = math.radians(az), math.radians(el)
        cam.location = (C.x + 5*math.sin(ar_)*math.cos(el_), C.y - 5*math.cos(ar_)*math.cos(el_), C.z + 5*math.sin(el_))
        cam.rotation_euler = (C - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
        p = os.path.join(tmp, "p%d.png" % len(tiles)); sc.render.filepath = p; bpy.ops.render.render(write_still=True); tiles.append(p)
    buf = np.ones((CW * 2, CW * 4, 4), np.float32)
    for i, p in enumerate(tiles):
        im = bpy.data.images.load(p); r_, c_ = divmod(i, 4); buf[(1 - r_) * CW:(2 - r_) * CW, c_ * CW:(c_ + 1) * CW] = np.array(im.pixels[:], np.float32).reshape(CW, CW, 4)
    sh = bpy.data.images.new("s", CW * 4, CW * 2); sh.pixels = buf.ravel(); sh.filepath_raw = CHECK; sh.file_format = 'PNG'; sh.save(); print("OF 確かめ", CHECK)
else:
    for fi, uv in fix.items():
        for l in bm.faces[fi].loops: l[uvL].uv = uv
    bm.to_mesh(m); bm.free(); m.update()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
    print("OF 書き出し", OUT)
