# -*- coding: utf-8 -*-
"""肩の服が髪の房に突き抜ける所で、髪の頂点を服の外へ押し出す。面は消さない。骨・重み・動き・絵はそのまま、髪の頂点の位置だけ。
   お嬢様（小学生編）は、待機・歩きで腕が下がると肩の服が持ち上がり、うしろの髪の房を突き抜けて、房に白い欠けができた
   （「肩口の髪の欠けは両肩、特に右が酷い」）。
   1) 箱（左右の肩）の中の髪の頂点（暗い面の頂点）と服の面（明るい面）を選ぶ
   2) CLIPS の全コマで、髪の頂点ごとに一番近い服の面を探し、服の外向き（体の中心の縦の線から離れる向き）に測った距離が
      MARGIN より小さい（＝服の中か、服にくっつきすぎ）なら、足りない分を「押し出す量」とする（コマの中で一番大きい値。上限 CAP）
   3) 押し出す向きは、素の形で、その一番近い服の面の外向き。押し出す量は、となりの髪の頂点となじませる（NIT 回）
      同じ位置の頂点（絵の切れ目）は一緒に動かす（片方だけ動かすと穴になる）
   実行: blender -b --factory-startup -P hairpush.py -- 入力.glb 出力.glb [--margin 0.004] [--cap 0.025] [--clips Idle,Walk_Child] [--nit 6]"""
import bpy, bmesh, sys, colorsys, collections, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
MARGIN = float(opt('--margin', 0.004)); CAP = float(opt('--cap', 0.025)); CLIPS = opt('--clips', 'Idle,Walk_Child').split(','); NIT = int(opt('--nit', 6))
SRC, OUT = a[0], a[1]
BOXES = [(-0.20, -0.06, -0.06, 0.08, 0.70, 0.86), (0.06, 0.20, -0.06, 0.08, 0.70, 0.86)]   # 右肩・左肩（x, y, z）
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data; MW = me.matrix_world; MI = MW.inverted()
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4); uvl = m.uv_layers.active.data
def fv(p):
    uv = np.mean([uvl[li].uv[:] for li in p.loop_indices], 0)
    return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])[2]
V = np.array([fv(p) for p in m.polygons])
P0 = [MW @ v.co for v in m.vertices]
def inb(c): return any(b[0] <= c.x <= b[1] and b[2] <= c.y <= b[3] and b[4] <= c.z <= b[5] for b in BOXES)
cloth = [p.index for p in m.polygons if V[p.index] >= 0.6 and inb(MW @ p.center)]
hairv = set()
for p in m.polygons:
    if V[p.index] < 0.4 and inb(MW @ p.center): hairv.update(p.vertices)
lightv = set(v for fi in cloth for v in m.polygons[fi].vertices)
hairv = sorted(hairv - lightv)   # 服と共有する頂点は動かさない
print("HP 髪の頂点 %d・服の面 %d" % (len(hairv), len(cloth)))
def joint(c, posed):
    # その側の肩の関節（腕の骨の根元）
    nm = 'RightArm' if c.x < 0 else 'LeftArm'
    return arm.matrix_world @ (arm.pose.bones[nm].head if posed else arm.data.bones[nm].head_local)
def outward(c, n, posed=True):
    # 服の面の外向き：肩の関節から離れる向きにそろえる（体の中心の縦の線を基準にしたら、肩のうしろで向きを取り違えて、半分近くが上限まで押し出された）
    r = c - joint(c, posed); return n if n.dot(r) >= 0 else -n
need = {}; nface = {}
# 動きの帯（NLA）は消さずにミュートする（消すと書き出した glb から動きがなくなった）
for tr in arm.animation_data.nla_tracks: tr.mute = True
for cn in CLIPS:
    act = next(x for x in bpy.data.actions if x.name.startswith(cn)); arm.animation_data.action = act
    f0, f1 = map(int, act.frame_range)
    for fr in range(f0, f1 + 1, 2):
        bpy.context.scene.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); em = me.evaluated_get(dg).to_mesh()
        vs = [MW @ v.co for v in em.vertices]
        tree = BVHTree.FromPolygons(vs, [list(em.polygons[i].vertices) for i in cloth], all_triangles=False)
        for vi in hairv:
            loc, nrm, idx, dist = tree.find_nearest(vs[vi], 0.04)
            if loc is None: continue
            n = outward(loc, nrm.normalized()); d = (vs[vi] - loc).dot(n)
            if d < MARGIN:
                k = min(MARGIN - d, CAP)
                if k > need.get(vi, 0): need[vi] = k; nface[vi] = cloth[idx]
        me.evaluated_get(dg).to_mesh_clear()
print("HP 押し出す髪の頂点 %d・一番大きい量 %.4f" % (len(need), max(need.values()) if need else 0))
# 素の形での押し出す向き
arm.animation_data.action = None
for tr in arm.animation_data.nla_tracks: tr.mute = False
bpy.context.view_layer.update()
N3 = MW.to_3x3().inverted().transposed()
disp = {}
for vi, k in need.items():
    p = m.polygons[nface[vi]]; n = outward(MW @ p.center, (N3 @ p.normal).normalized(), posed=False)
    disp[vi] = n * k
# となりの髪の頂点となじませる（押し出さない頂点も、となりが動けば少し動く）
bm = bmesh.new(); bm.from_mesh(m); bm.verts.ensure_lookup_table()
hs = set(hairv); D = {vi: disp.get(vi, Vector()) for vi in hairv}
for _ in range(NIT):
    nd = {}
    for vi in hairv:
        ns = [e.other_vert(bm.verts[vi]).index for e in bm.verts[vi].link_edges]; ns = [j for j in ns if j in hs]
        avg = sum((D[j] for j in ns), Vector()) / len(ns) if ns else Vector()
        # 押し出しが要る頂点は、少なくとも要る量は保つ
        v2 = D[vi] * 0.5 + avg * 0.5
        if vi in disp and v2.length < disp[vi].length: v2 = disp[vi]
        nd[vi] = v2
    D = nd
# 同じ位置の頂点は一緒に
posg = collections.defaultdict(list)
for v in bm.verts: posg[tuple(round(x, 6) for x in v.co)].append(v)
done = set(); mx_ = 0.0; nmv = 0
for vi in hairv:
    if D[vi].length < 1e-5: continue
    key = tuple(round(x, 6) for x in bm.verts[vi].co)
    if key in done: continue
    done.add(key); dl = MI.to_3x3() @ D[vi]
    for v in posg[key]:
        if v.index in lightv: continue
        v.co = v.co + dl
    mx_ = max(mx_, D[vi].length); nmv += 1
print("HP 動かした位置 %d・一番動いた長さ %.4f" % (nmv, mx_))
bm.to_mesh(m); bm.free(); m.update()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("HP 書き出し", OUT)
