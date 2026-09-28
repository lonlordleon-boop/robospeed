# -*- coding: utf-8 -*-
"""
GLB を読み込み、腿のボーンが担当している頂点の高さ分布を Blender 自身のデータで出す。
あわせて、ウェイトペイントで開ける .blend を保存する。
  実行: blender --background --factory-startup --python inspect_weights.py -- 入力.glb 出力.blend
注意: glTF 読み込み後の Blender は Z が高さ（元データの Y）。
"""
import bpy, sys, os

argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
SRC = argv[0]
DST = argv[1] if len(argv) > 1 else ""

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)

mesh = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
arm  = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
print("MESH", mesh.name if mesh else None, "ARMATURE", arm.name if arm else None)
print("VERTS", len(mesh.data.vertices))

# 頂点グループ名 → 番号
gi = {g.name: g.index for g in mesh.vertex_groups}
print("GROUPS", len(gi))

LEG  = [gi[n] for n in ("LeftUpLeg","RightUpLeg") if n in gi]
mw = mesh.matrix_world
zs = [(mw @ v.co).z for v in mesh.data.vertices]
z0, z1 = min(zs), max(zs)
H = z1 - z0
print("HEIGHT %.4f" % H)

# 骨の高さ（比較用）
if arm:
    aw = arm.matrix_world
    for b in ("Hips","Spine02","Spine01","Spine","neck","LeftShoulder","Head"):
        if b in arm.data.bones:
            z = (aw @ arm.data.bones[b].head_local).z
            print("BONE %-14s %5.1f%%" % (b, 100*(z-z0)/H))

# 高さ帯ごとの腿ウェイト
B = 20
tot = [0.0]*B; cnt = [0]*B; mx = [0.0]*B
for i, v in enumerate(mesh.data.vertices):
    z = zs[i]
    b = min(B-1, int((z - z0) / H * B))
    w = 0.0
    for g in v.groups:
        if g.group in LEG:
            w += g.weight
    tot[b] += w; cnt[b] += 1
    if w > mx[b]: mx[b] = w
print("BAND  高さ%   平均   最大   頂点数")
for i in range(B):
    if cnt[i] < 5: continue
    print("BAND %5.0f%%  %.3f  %.3f  %6d  %s" %
          (100*(i+0.5)/B, tot[i]/cnt[i], mx[i], cnt[i], "#"*int(tot[i]/cnt[i]*60)))

if DST:
    # 開いたらすぐ腿のウェイトが見えるようにしておく
    if "LeftUpLeg" in mesh.vertex_groups:
        mesh.vertex_groups.active_index = mesh.vertex_groups["LeftUpLeg"].index
    for o in bpy.data.objects: o.select_set(False)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print("SAVED", DST)
