# -*- coding: utf-8 -*-
"""髪の房の欠け（房のふちが欠けて、下の服が白く見える所）に、髪の色の小さなつぎ当ての面を置く。面は消さない。
   お嬢様（小学生編）は右肩の前で、髪の房のふちがぎざぎざに欠けて白い服が見え、「欠けてる」と言われた。
   ふちの辺をつないで埋めようとしたが、肩の内側は細かい切れ端が入り乱れていて（ふちの辺 128・鎖 19）、つなげなかった。
   1) 中心 C・向き N（服の表面の向き）・半径 R の八角形を、服から OFF だけ浮かせて置く（表裏どちらからも描かれる）
   2) 絵の位置（UV）は、指定の髪の面の真ん中の 1 点（無地の髪の色）。骨の重みは、その髪の面の頂点の平均
      （つぎ当てはその房と一緒に動く。服と一緒に動かすと、頭が向きを変えた時に房から離れる）
   R は「横の半径,縦の半径」でもよい（房に沿った縦長のつぎ当て。丸いと肩の上で塊に見えた）
   実行: blender -b --factory-startup -P hairpatch.py -- 入力.glb 出力.glb cx,cy,cz nx,ny,nz R[,RV] OFF 髪の面番号"""
import bpy, bmesh, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]
C = Vector(tuple(map(float, a[2].split(',')))); N = Vector(tuple(map(float, a[3].split(',')))).normalized(); OFF = float(a[5]); HF = int(a[6])
RR = list(map(float, a[4].split(','))); R = RR[0]; RV = RR[1] if len(RR) > 1 else RR[0]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data; MW = me.matrix_world; MI = MW.inverted()
bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table(); uvL = bm.loops.layers.uv.active; dfl = bm.verts.layers.deform.active
hf = bm.faces[HF]; uc = sum((l[uvL].uv for l in hf.loops), Vector((0, 0))) / len(hf.loops)
w = {}
for v in hf.verts:
    for g, x in v[dfl].items(): w[g] = w.get(g, 0.0) + x / len(hf.verts)
u = N.cross(Vector((0, 0, 1)))
if u.length < 1e-6: u = N.cross(Vector((1, 0, 0)))
u.normalize(); v_ = N.cross(u).normalized(); c = C + N * OFF
vs = []
for k in range(8):
    t = 2 * math.pi * k / 8; p = c + u * (R * math.cos(t)) + v_ * (RV * math.sin(t))
    nv = bm.verts.new(MI @ p); vs.append(nv)
cv = bm.verts.new(MI @ c)
for nv in vs + [cv]:
    d = nv[dfl]
    for g, x in w.items(): d[g] = x
n = 0
for k in range(8):
    f = bm.faces.new((cv, vs[k], vs[(k + 1) % 8])); f.material_index = hf.material_index; f.smooth = True
    for l in f.loops: l[uvL].uv = uc
    f.normal_update()
    if f.normal.dot(MI.to_3x3() @ N) < 0: bmesh.utils.face_flip(f)
    n += 1
print("HT つぎ当て %d 面（中心 %s・半径 %.3f×%.3f・浮かせ %.3f・重み %s）" % (n, tuple(round(x, 3) for x in C), R, RV, OFF, {me.vertex_groups[g].name: round(x, 2) for g, x in w.items()}))
bm.to_mesh(m); bm.free(); m.update()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("HT 書き出し", OUT)
