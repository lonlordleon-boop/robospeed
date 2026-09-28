# -*- coding: utf-8 -*-
"""腕の服で、裏返った面（面の向きが腕の骨の線の方＝内側を向く）を直す。面は消さない。骨・重み・動き・絵はそのまま、頂点の位置だけ。
   お嬢様（小学生編）は右袖の前（f3113）が裏返っていて、となりの面と折り重なっていた。ツールは面の裏も描くので、
   裏返った面が暗く沈んで穴のように見えた（「右腕穴開いてる」）。真ん中の頂点が、境目の線から 0.1mm しか離れていなかった。
   1) 腕の骨（BONE の根元 → 次の骨の根元）の近く（RMAX 以内）で、外向き（面の向き・骨の線から外への向き）が負の面を探す
   2) その面の頂点を 1 つずつ、動かす候補の位置（まわり SR の格子）へ動かしてみて、その頂点が付く面が全部 外向き ≥ 0.3 になる
      一番近い位置を選ぶ（同じ位置の頂点は一緒に動かす）
   実行: blender -b --factory-startup -P unflip.py -- 入力.glb 出力.glb [BONE RightArm] [NEXT RightForeArm] [RMAX 0.09] [SR 0.012] --box x0,x1,y0,y1,z0,z1
   お嬢様の右袖の前: --box -0.13,-0.09,-0.07,-0.045,0.70,0.80"""
import bpy, bmesh, sys, itertools
from mathutils import Vector
from mathutils.geometry import intersect_point_line
a = sys.argv[sys.argv.index("--")+1:]
# --box x0,x1,y0,y1,z0,z1：探す範囲。腕のまわり全体で探したら、袖の内側・胴・髪など、内側を向くのが正しい面まで 403 面拾った
BOX = None
if '--box' in a: i = a.index('--box'); BOX = tuple(map(float, a[i+1].split(','))); a = a[:i] + a[i+2:]
SRC, OUT = a[0], a[1]
BONE = a[2] if len(a) > 2 else 'RightArm'; NEXT = a[3] if len(a) > 3 else 'RightForeArm'
RMAX = float(a[4]) if len(a) > 4 else 0.09; SR = float(a[5]) if len(a) > 5 else 0.012
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
MW = me.matrix_world; MI = MW.inverted()
def bh(n): return arm.matrix_world @ arm.data.bones[n].head_local
A, F = bh(BONE), bh(NEXT)
# 動かした頂点が付く面の判定は、範囲の少し外の面も含める（範囲の外の面を裏返さないため）
def near_wide(f):
    c = MW @ f.calc_center_median(); q, t = intersect_point_line(c, A, F)
    return -0.1 <= t <= 1.1 and (c - q).length <= RMAX
bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
def outward(f, override=None):
    ps = [MW @ (override.get(v, v.co) if override else v.co) for v in f.verts]
    n = (ps[1] - ps[0]).cross(ps[2] - ps[0])
    if n.length < 1e-12: return -1.0
    c = sum(ps, Vector()) / len(ps); q, t = intersect_point_line(c, A, F)
    r = c - q
    return n.normalized().dot(r.normalized()) if r.length > 1e-9 else 0.0
def near(f):
    c = MW @ f.calc_center_median(); q, t = intersect_point_line(c, A, F)
    if BOX and not (BOX[0] <= c.x <= BOX[1] and BOX[2] <= c.y <= BOX[3] and BOX[4] <= c.z <= BOX[5]): return False
    return -0.1 <= t <= 1.1 and (c - q).length <= RMAX
key = {}
for v in bm.verts: key.setdefault(tuple(round(x, 6) for x in v.co), []).append(v)
bad = [f for f in bm.faces if near(f) and outward(f) < 0]
print("UF 裏返った面 %d: %s" % (len(bad), [f.index for f in bad]))
steps = [i * SR / 4 for i in range(-4, 5)]
fixed = 0
for f in bad:
    if outward(f) >= 0: continue
    best = None
    for v in f.verts:
        grp = key[tuple(round(x, 6) for x in v.co)]
        faces = {g for u in grp for g in u.link_faces}
        # 服の面でない（別の層・髪）面は数えない：腕の近くの面だけで判定
        # 外を向いている面は、動かしたあとも min(0.3, 今の値) 以上、直したい面は 0.3 以上
        faces = [(g, 0.3 if g is f else min(0.3, outward(g))) for g in faces if g is f or (near_wide(g) and outward(g) >= 0)]
        p0 = MW @ v.co
        for dx, dy, dz in itertools.product(steps, steps, steps):
            d = Vector((dx, dy, dz))
            if d.length > SR: continue
            co = MI @ (p0 + d); ov = {u: co for u in grp}
            if all(outward(g, ov) >= lim for g, lim in faces):
                if best is None or d.length < best[0]: best = (d.length, grp, co)
    if best:
        for u in best[1]: u.co = best[2]
        fixed += 1
        print("UF f%d：頂点を %.1fmm 動かして直した" % (f.index, best[0] * 1000))
    else:
        print("UF f%d：直せる位置が見つからなかった" % f.index)
print("UF 直した面 %d / %d" % (fixed, len(bad)))
bm.to_mesh(m); bm.free(); m.update()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("UF 書き出し", OUT)
