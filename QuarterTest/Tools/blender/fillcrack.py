# -*- coding: utf-8 -*-
"""箱の中の小さな穴（片側にしか面がない辺で囲まれた、頂点 MAXN 個以下の輪）に面を足して塞ぐ。面は消さない。
   お嬢様（小学生編）は右袖の前に、生成の時からの細い隙間が 2 つあった（3 頂点の細い三角と 4 頂点の四角）。
   止まっている時は線のように細いが、動くと開き、うしろの肩や髪が見えて穴に見えた（「右腕の穴も塞がってない」）。
   1) 同じ位置の頂点（絵の切れ目）を 1 つとみなして、片側にしか面がない辺を探し、輪にまとめる
   2) 輪ごとに、となりの面が使っている実際の頂点で面を作る。絵の位置（UV）は、となりの面の真ん中の 1 点にそろえる
      （その面と同じ色の無地になる）。面の向きは、となりの面の向きにそろえる
   実行: blender -b --factory-startup -P fillcrack.py -- 入力.glb 出力.glb x0,x1,y0,y1,z0,z1 [MAXN 6]"""
import bpy, bmesh, sys, collections
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
BOX = tuple(map(float, a[2].split(','))); MAXN = int(a[3]) if len(a) > 3 else 6
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data; MW = me.matrix_world
bm = bmesh.new(); bm.from_mesh(m); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
uvL = bm.loops.layers.uv.active
def key(v): return tuple(round(x, 4) for x in (MW @ v.co))
def inb(c): return BOX[0] <= c.x <= BOX[1] and BOX[2] <= c.y <= BOX[3] and BOX[4] <= c.z <= BOX[5]
cnt = collections.Counter(); owner = {}
for f in bm.faces:
    vs = f.verts
    for i in range(len(vs)):
        a_, b_ = vs[i], vs[(i + 1) % len(vs)]
        e = tuple(sorted((key(a_), key(b_)))); cnt[e] += 1; owner.setdefault(e, []).append((f, a_, b_))
open_e = [e for e, n in cnt.items() if n == 1 and inb((Vector(e[0]) + Vector(e[1])) / 2)]
adj = collections.defaultdict(list)
for e in open_e: adj[e[0]].append(e[1]); adj[e[1]].append(e[0])
# 輪にまとめる
seen = set(); loops = []
for s in list(adj):
    if s in seen: continue
    loop = [s]; seen.add(s); prev = None; cur = s
    while True:
        nx = [n for n in adj[cur] if n != prev]
        if not nx: break
        n = nx[0]
        if n == s: loops.append(loop); break
        if n in seen: break
        loop.append(n); seen.add(n); prev, cur = cur, n
print("FC 穴のふちの辺 %d・輪 %d" % (len(open_e), len(loops)))
added = 0
for loop in loops:
    if len(loop) > MAXN or len(loop) < 3: continue
    # 各位置で、となりの面が使っている実際の頂点と UV
    pick = {}; nrm = Vector()
    for i in range(len(loop)):
        e = tuple(sorted((loop[i], loop[(i + 1) % len(loop)])))
        f, a_, b_ = owner[e][0]; nrm += f.normal
        for v in (a_, b_):
            k = key(v)
            if k not in pick:
                lp = next(l for l in f.loops if l.vert == v); pick[k] = (v, lp[uvL].uv.copy())
    vs = [pick[k][0] for k in loop]
    if len(set(vs)) < len(vs): continue
    try:
        nf = bm.faces.new(vs)
    except ValueError:
        continue
    nf.normal_update()
    if nf.normal.dot(nrm) < 0:
        bmesh.utils.face_flip(nf)
    # 絵の位置は、となりの面の真ん中の 1 点にそろえる（角ごとに写したら、絵の島をまたいで関係ない所を読み、黒い縞が出た）
    f0 = owner[tuple(sorted((loop[0], loop[1])))][0][0]
    uc = sum((l[uvL].uv for l in f0.loops), Vector((0, 0))) / len(f0.loops)
    for l in nf.loops: l[uvL].uv = uc
    nf.material_index = owner[tuple(sorted((loop[0], loop[1])))][0][0].material_index
    nf.smooth = True; added += 1
print("FC 塞いだ穴 %d" % added)
bm.to_mesh(m); bm.free(); m.update()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("FC 書き出し", OUT)
