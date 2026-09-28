# -*- coding: utf-8 -*-
"""GLB に埋め込まれたテクスチャを PNG として取り出す。
   実行: blender -b --factory-startup -P extract_tex.py -- 入力.glb 出力.png"""
import bpy, sys, os
a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
imgs = [i for i in bpy.data.images if i.size[0] > 4 and i.size[1] > 4]
print("IMAGES", [(i.name, i.size[0], i.size[1]) for i in imgs])
if not imgs:
    print("NO_IMAGE"); sys.exit(0)
img = max(imgs, key=lambda i: i.size[0] * i.size[1])
img.file_format = 'PNG'
os.makedirs(os.path.dirname(DST), exist_ok=True)
img.filepath_raw = DST
img.save()
print("SAVED", DST, img.size[0], "x", img.size[1], os.path.getsize(DST))
