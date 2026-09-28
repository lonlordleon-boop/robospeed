# -*- coding: utf-8 -*-
"""髪・リボン（絵の色で判定）の頂点の重みを、頭の骨（Head）だけにする。
   T字で骨を入れると、腕のすぐ上にあるポニーテールに腕の重みが入り、腕を動かすと髪と顔が引っ張られた。
   判定：首の関節より上、左右 0.30 以内、絵の色が「色相 12〜70度・彩度 0.35 以上」（髪のオレンジ茶・リボンの黄）。
   上着の赤（色相 0〜10度）と肌（彩度が低い）は外れる。
   実行: blender -b --factory-startup -P hairweight.py -- 入力.glb 出力.glb [確認用の色.png]"""
import bpy, sys, colorsys, numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC, OUT = a[0], a[1]; ZMIN = float(a[2]) if len(a) > 2 else 0.86
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data: arm.animation_data.action = None
for ac in list(bpy.data.actions): bpy.data.actions.remove(ac)
for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
neckz = (arm.matrix_world @ arm.pose.bones['neck'].head).z
uvl = m.uv_layers.active.data
vuv = np.zeros((len(m.vertices), 2)); cnt = np.zeros(len(m.vertices))
for p in m.polygons:
    for li in p.loop_indices:
        vi = m.loops[li].vertex_index; vuv[vi] += uvl[li].uv; cnt[vi] += 1
vuv /= np.maximum(cnt, 1)[:, None]
MW = me.matrix_world
hair = np.zeros(len(m.vertices), bool)
cand = np.zeros(len(m.vertices), bool)
for v in m.vertices:
    w = MW @ v.co
    if w.z < ZMIN or abs(w.x) > 0.40: continue
    u, t = vuv[v.index]
    c = px[int(np.clip(t, 0, .9999) * H_), int(np.clip(u, 0, .9999) * W_), :3]
    h, s, val = colorsys.rgb_to_hsv(*c)
    jacket = (h < 12/360 or h > 340/360) and s > 0.45
    light = s < 0.33 and val > 0.55          # 肌・Tシャツ・ファスナー
    hw = sum(e.weight for e in v.groups if me.vertex_groups[e.group].name in ('Head','head_end','headfront'))
    # 顔の横より外（ポニーテール）は、頭の重みが無くても候補にする（房の内側は腕の重みだけのことがあった）
    aw = sum(e.weight for e in v.groups if me.vertex_groups[e.group].name.endswith(('Shoulder','Arm','ForeArm','Hand')))
    # 腕の重みがほとんど（0.7 以上）で頭の重みが無い頂点は袖とみなして外す（左肩の袖が髪にされて飛び出した）
    cand[v.index] = (not jacket) and (not light) and (hw >= 0.05 or (abs(w.x) >= 0.06 and w.z >= 0.90 and aw < 0.7))
    # 髪の影（暗い茶）も含める。もともと頭の重みが少しでもある頂点だけ（襟や袖に乗った髪色の点は外す）
    if cand[v.index] and (hw >= 0.15 or (abs(w.x) >= 0.06 and w.z >= 0.90 and 12/360 <= h <= 70/360)): hair[v.index] = True
# まわり2つ分へ広げる（候補の中だけ）。毛の房の内側の影を取りこぼさないため
nb = [[] for _ in m.vertices]
for e in m.edges:
    i, j = e.vertices; nb[i].append(j); nb[j].append(i)
for _ in range(4):
    add = [j for i in np.nonzero(hair)[0] for j in nb[i] if cand[j] and not hair[j]]
    hair[add] = True
print("HW 首の関節の高さ %.3f  髪と判定した頂点 %d / %d" % (neckz, hair.sum(), len(m.vertices)))
head = me.vertex_groups.get('Head')
# 頭の重みが半分以上ある頂点（顔など）から、腕・肩の骨の重みを外す（1〜2%でも腕を動かすと顔が数mm引っ張られた）
ARMB = {me.vertex_groups[n].index for n in ('LeftShoulder','LeftArm','LeftForeArm','LeftHand','RightShoulder','RightArm','RightForeArm','RightHand') if n in me.vertex_groups}
HB = {me.vertex_groups[n].index for n in ('Head','head_end','headfront') if n in me.vertex_groups}
nclean = 0
for v in m.vertices:
    if hair[v.index]: continue
    hw = sum(e.weight for e in v.groups if e.group in HB)
    if hw < 0.4: continue
    rm = [e.group for e in v.groups if e.group in ARMB]
    if not rm: continue
    for g in rm: me.vertex_groups[g].remove([v.index])
    tot = sum(e.weight for e in v.groups)
    for e in v.groups: e.weight = e.weight / tot
    nclean += 1
print("HW 腕の重みを外した頭の頂点", nclean)
for v in m.vertices:
    if not hair[v.index]: continue
    for e in list(v.groups):
        me.vertex_groups[e.group].remove([v.index])
    head.add([v.index], 1.0, 'REPLACE')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=False, export_skins=True, export_yup=True)
print("HW 書き出し", OUT)
