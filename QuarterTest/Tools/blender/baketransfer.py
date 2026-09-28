# -*- coding: utf-8 -*-
"""別のモデルの色を、こちらのモデルの UV へ焼き移す。
   作り直したテクスチャは UV の配置が変わってしまうため、
   形の近さで対応を取り、こちらの UV に合わせた1枚の絵として焼き直す。
   実行: blender -b --factory-startup -P baketransfer.py -- こちら.glb 相手.glb 出力.png [解像度]"""
import bpy, sys
a=sys.argv[sys.argv.index("--")+1:]
DST_GLB, SRC_GLB, OUT = a[0], a[1], a[2]
RES=int(a[3]) if len(a)>3 else 2048
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=DST_GLB)
dst=[o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith("Icosphere")][0]
dst.name="TARGET"
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
before=set(o.name for o in bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
src=[o for o in bpy.data.objects if o.type=='MESH' and o.name not in before]
if not src: raise SystemExit("相手のメッシュが見つからない")
src=src[0]; src.name="SOURCE"
print("BT こちら %d頂点 / 相手 %d頂点"%(len(dst.data.vertices),len(src.data.vertices)))
# 相手は大きさと位置が正規化されていることがあるので、こちらの箱に合わせる
import numpy as np
def bbox(o):
    P=np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices]); return P.min(0),P.max(0)
dl,dh=bbox(dst); sl,sh=bbox(src)
k=float((dh[2]-dl[2])/max(1e-9,(sh[2]-sl[2])))
src.scale=(k,k,k); bpy.context.view_layer.update()
sl,sh=bbox(src)
off=((dl+dh)/2)-((sl+sh)/2)
src.location=(float(off[0]),float(off[1]),float(off[2])); bpy.context.view_layer.update()
sl,sh=bbox(src)
print("BT 相手を %.4f 倍して位置合わせ → 最小%s 最大%s"%(k,np.round(sl,3),np.round(sh,3)))
# 焼き先の画像を作り、こちらの材質に貼る
img=bpy.data.images.new("baked",RES,RES); img.generated_color=(0,0,0,1)
for m in dst.data.materials:
    if not m.use_nodes: m.use_nodes=True
    n=m.node_tree.nodes.new('ShaderNodeTexImage'); n.image=img
    m.node_tree.nodes.active=n
sc=bpy.context.scene
sc.render.engine='CYCLES'
sc.cycles.samples=1
sc.cycles.device='CPU'
sc.render.bake.use_selected_to_active=True
sc.render.bake.cage_extrusion=0.001
sc.render.bake.max_ray_distance=0.10
sc.render.bake.margin=32
sc.render.bake.use_pass_direct=False
sc.render.bake.use_pass_indirect=False
sc.render.bake.use_pass_color=True
for o in bpy.data.objects: o.select_set(False)
src.select_set(True); dst.select_set(True)
bpy.context.view_layer.objects.active=dst
bpy.ops.object.bake(type='DIFFUSE')
img.filepath_raw=OUT; img.file_format='PNG'; img.save()
print("BT 焼き出し",OUT)
