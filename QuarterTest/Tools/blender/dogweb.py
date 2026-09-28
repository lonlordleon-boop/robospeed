# -*- coding: utf-8 -*-
"""ブラウザ試作用に、犬の glb を軽くする。

   生成したメッシュは 3万1千三角形・2048の絵で 3.7MB ある。
   park12.html は glb を文字にして埋め込む作りなので、そのままだと 5MB になりページが重い。
   画面の中の犬は高さ40画素ほどなので、面と絵を減らしても見た目は変わらない。

   ・面を減らす（Decimate。骨の重みは自動で引き継がれる）
   ・絵を小さくする
   ・変形用の DEF- の骨だけで書き出す

   Unity へ持っていく時は、減らす前の dog_run.glb を使うこと。

   実行: blender -b -P dogweb.py -- 入力.glb 出力.glb [三角形の数] [絵の大きさ]
"""
import bpy, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(a[0])
OUT = os.path.abspath(a[1])
TRIS = int(a[2]) if len(a) > 2 else 8000
TEX = int(a[3]) if len(a) > 3 else 1024

def log(s):
    print("[web] " + str(s))

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=SRC)
mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
rig = next((o for o in bpy.context.scene.objects if o.type == 'ARMATURE'), None)
before = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
log("読み込み: 三角形 %d / 頂点 %d / 骨 %s" % (before, len(mesh.data.vertices),
                                                len(rig.data.bones) if rig else 0))

# ---------------------------------------------------------------- 面を減らす
bpy.context.view_layer.objects.active = mesh
mod = mesh.modifiers.new('dec', 'DECIMATE')
mod.ratio = min(1.0, TRIS / float(before))
bpy.ops.object.modifier_apply(modifier=mod.name)
after = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
log("面を減らした: %d → %d 三角形（%.0f%%）" % (before, after, 100.0 * after / before))

# ---------------------------------------------------------------- 絵を小さくする
for mat in mesh.data.materials:
    if not mat or not mat.use_nodes:
        continue
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image:
            w, h = n.image.size
            if max(w, h) > TEX:
                n.image.scale(TEX, TEX)
                log("絵を小さくした: %dx%d → %dx%d" % (w, h, TEX, TEX))

# ---------------------------------------------------------------- 動きを棚に上げ直す
# 読み込むと動きは「アクション」になるが、棚（NLA）に無いものは書き出されない。
# 2つ以上の動きが入っている時は、必ず全部を棚に上げてから出すこと
if rig:
    if not rig.animation_data:
        rig.animation_data_create()
    have = {t.name for t in rig.animation_data.nla_tracks}
    for ac in bpy.data.actions:
        if ac.name in have:
            continue
        tr = rig.animation_data.nla_tracks.new()
        tr.name = ac.name
        tr.strips.new(ac.name, 1, ac)
    rig.animation_data.action = None
    log("動き: " + ", ".join(t.name for t in rig.animation_data.nla_tracks))

# ---------------------------------------------------------------- 書き出し
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True)
if rig:
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True,
                          export_animations=True, export_skins=True, export_yup=True,
                          export_frame_range=True, export_anim_single_armature=True,
                          export_animation_mode='ACTIONS',
                          export_def_bones=True, export_optimize_animation_size=False,
                          export_image_format='JPEG', export_jpeg_quality=88)
log("書き出し: %s (%.2f MB)" % (OUT, os.path.getsize(OUT) / 1048576.0))
print("[web] DONE")
