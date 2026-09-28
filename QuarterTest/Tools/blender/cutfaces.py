# -*- coding: utf-8 -*-
"""指定した名前のメッシュから、箱の中にある面を消す（部品に付いてきた小さなゴミ取り用）。

   カツラの部品には、生成時に首元へ飛び散った小さな欠片が残ることがある。
   面の中心が箱（Blender 座標・メートル、world）に入る面を消し、浮いた頂点も消す。
   骨・重み・アニメ・材質はそのまま。Blender で読み直して書き出すだけ。

   実行: blender -b --factory-startup -P cutfaces.py -- 入力.glb 出力.glb メッシュ名の先頭 "x0,x1,y0,y1,z0,z1[;...]"
   例:   ... -- doll.glb out.glb hair "-0.10,0.10,-0.10,0.10,0.75,0.87"
"""
import bpy, sys, os
a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, NAME = a[0], a[1], a[2]
BOXES = [[float(v) for v in b.split(',')] for b in a[3].split(';')]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
obj = next(o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(NAME))
mesh = obj.data; MW = obj.matrix_world
def inbox(p):
    return any(b[0] <= p.x <= b[1] and b[2] <= p.y <= b[3] and b[4] <= p.z <= b[5] for b in BOXES)
for o in bpy.data.objects: o.select_set(False)
obj.select_set(True); bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
n = 0
for f in mesh.polygons:
    if inbox(MW @ f.center): f.select = True; n += 1
print("CF %s: 箱の中の面 %d 枚を消す（全 %d 枚）" % (obj.name, n, len(mesh.polygons)))
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='FACE')
bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.delete_loose(); bpy.ops.object.mode_set(mode='OBJECT')
print("CF 残った面 %d、頂点 %d" % (len(mesh.polygons), len(mesh.vertices)))
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB', export_animations=True, export_skins=True, export_yup=True)
print("CF 書き出し", DST, os.path.getsize(DST))
