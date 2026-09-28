# -*- coding: utf-8 -*-
"""新しく貼り直したメッシュへ、今のモデルの骨・重み・アニメをそのまま移す。
   テクスチャを今のUVへ焼き直すより、絵をそのまま使えるので崩れない。
   重みは「一番近い頂点から写す」方式。形はほぼ同じなので正確に写る。
   実行: blender -b --factory-startup -P transferrig.py -- 今の.glb 新しい.glb 出力.glb"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
OLD,NEW,OUT=a[0],a[1],a[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=OLD)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
mold=next(o for o in bpy.data.objects if o.type=='MESH')
mold.name="OLDMESH"
before=set(o.name for o in bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=NEW)
news=[o for o in bpy.data.objects if o.name not in before]
mnew=[o for o in news if o.type=='MESH'][0]; mnew.name="NEWMESH"
def bbox(o):
    P=np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices]); return P.min(0),P.max(0)
dl,dh=bbox(mold); sl,sh=bbox(mnew)
k=float((dh[2]-dl[2])/max(1e-9,(sh[2]-sl[2])))
mnew.scale=(k,k,k); bpy.context.view_layer.update()
sl,sh=bbox(mnew)
off=((dl+dh)/2)-((sl+sh)/2)
mnew.location=(float(off[0]),float(off[1]),float(off[2])); bpy.context.view_layer.update()
sl,sh=bbox(mnew)
print("TR 新しいメッシュを %.4f 倍して位置合わせ  最小%s 最大%s"%(k,np.round(sl,3),np.round(sh,3)))
# 親子や変換を確定させる
for o in bpy.data.objects: o.select_set(False)
mnew.select_set(True); bpy.context.view_layer.objects.active=mnew
mnew.parent=None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
# 重みを写す
for o in bpy.data.objects: o.select_set(False)
mnew.select_set(True); mold.select_set(True)
bpy.context.view_layer.objects.active=mold      # 写す元＝今のメッシュ
bpy.ops.object.data_transfer(data_type='VGROUP_WEIGHTS',
                             vert_mapping='NEAREST', layers_select_src='ALL', layers_select_dst='NAME')
print("TR 重みを写した頂点グループ %d 個"%len(mnew.vertex_groups))
# 骨に付ける
for o in bpy.data.objects: o.select_set(False)
mnew.select_set(True); arm.select_set(True)
bpy.context.view_layer.objects.active=arm
bpy.ops.object.parent_set(type='ARMATURE_NAME')   # 骨に付ける（頂点グループはそのまま使う）
print("TR 骨に付けた: 親=%s モディファイア=%s"%(mnew.parent.name if mnew.parent else 'なし',[x.type for x in mnew.modifiers]))
# 古いメッシュを消す
bpy.data.objects.remove(mold, do_unlink=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_animations=True, export_skins=True,
                          export_apply=False, export_yup=True)
import os
print("TR 書き出し", OUT, os.path.getsize(OUT))
