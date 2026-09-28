# -*- coding: utf-8 -*-
"""貼り直したメッシュへ、今のモデルの骨・重み・アニメを移す。
   両者の頂点は位置が完全に一致しているので、位置で照合して重みをそのまま写す。
   （近さで写すと、A字ポーズでは手と腿が近いため、手に腿の重みが乗って壊れる）
   実行: blender -b --factory-startup -P transferrig2.py -- 今の.glb 新しい.glb 出力.glb"""
import bpy, sys, mathutils
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
OLD,NEW,OUT=a[0],a[1],a[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=OLD)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
mold=next(o for o in bpy.data.objects if o.type=='MESH'); mold.name="OLDMESH"
before=set(o.name for o in bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=NEW)
mnew=[o for o in bpy.data.objects if o.type=='MESH' and o.name not in before][0]; mnew.name="NEWMESH"
A=np.array([tuple(mold.matrix_world@v.co) for v in mold.data.vertices])
B=np.array([tuple(mnew.matrix_world@v.co) for v in mnew.data.vertices])
k=float((A[:,2].max()-A[:,2].min())/(B[:,2].max()-B[:,2].min()))
mnew.scale=(k,k,k); bpy.context.view_layer.update()
B=np.array([tuple(mnew.matrix_world@v.co) for v in mnew.data.vertices])
off=((A.min(0)+A.max(0))/2)-((B.min(0)+B.max(0))/2)
mnew.location=(float(off[0]),float(off[1]),float(off[2])); bpy.context.view_layer.update()
B=np.array([tuple(mnew.matrix_world@v.co) for v in mnew.data.vertices])
print("TR 位置合わせ 倍率%.4f  ずれ最大 %.5f"%(k, float(np.abs(np.array([A.min(0),A.max(0)])-np.array([B.min(0),B.max(0)])).max())))
kd=mathutils.kdtree.KDTree(len(A))
for i,p in enumerate(A): kd.insert(mathutils.Vector(p),i)
kd.balance()
# 今のメッシュの重みを取り出す
gname={g.index:g.name for g in mold.vertex_groups}
oldw=[[] for _ in range(len(mold.data.vertices))]
for v in mold.data.vertices:
    for g in v.groups:
        if g.weight>0: oldw[v.index].append((gname[g.group], g.weight))
# 新しいメッシュに同じ名前の頂点グループを作る
for n in sorted(set(gname.values())):
    if n not in mnew.vertex_groups: mnew.vertex_groups.new(name=n)
far=0
for vi,p in enumerate(B):
    co,i,dist=kd.find(mathutils.Vector(p))
    if dist>0.002: far+=1
    for n,w in oldw[i]:
        mnew.vertex_groups[n].add([vi], w, 'REPLACE')
print("TR 重みを写した %d 頂点（遠かったもの %d）"%(len(B),far))
mnew.parent=None
for o in bpy.data.objects: o.select_set(False)
mnew.select_set(True); bpy.context.view_layer.objects.active=mnew
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in bpy.data.objects: o.select_set(False)
mnew.select_set(True); arm.select_set(True)
bpy.context.view_layer.objects.active=arm
bpy.ops.object.parent_set(type='ARMATURE_NAME')
bpy.data.objects.remove(mold, do_unlink=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True)
import os
print("TR 書き出し", OUT, os.path.getsize(OUT))
