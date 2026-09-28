# -*- coding: utf-8 -*-
"""髪の頂点が、テクスチャのどの色を拾っているかを調べる。
   髪＝頭の重みが強く、頭の骨より上か横にあり、周りが茶色の面。肌色を拾っている頂点があれば場所を出す。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; TEX = a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
arm  = next(o for o in bpy.data.objects if o.type=='ARMATURE')
img = bpy.data.images.load(TEX); W,Hh = img.size
px = np.array(img.pixels[:]).reshape(Hh,W,4)
me = mesh.data; uvl = me.uv_layers.active.data
P=np.array([tuple(mesh.matrix_world @ v.co) for v in me.vertices])
Hgt=P[:,2].max()-P[:,2].min()
headz=(arm.matrix_world@arm.pose.bones['Head'].head).z
def col(uv):
    x=int(np.clip(uv[0],0,0.9999)*W); y=int(np.clip(uv[1],0,0.9999)*Hh)
    return px[y,x,:3]
# 面ごとに、頂点の平均色で「茶＝髪」「肌」を判定
brown=0; skin=0; mixed=[]
for poly in me.polygons:
    cs=[col(uvl[li].uv) for li in poly.loop_indices]
    z=np.mean([P[me.loops[li].vertex_index][2] for li in poly.loop_indices])
    if z < headz: continue
    cs=np.array(cs)
    def is_skin(c): return c[0]>0.75 and c[1]>0.55 and c[2]>0.45 and c[0]-c[2]<0.45 and c[1]>c[2]*0.9
    def is_hair(c): return c[0]>0.25 and c[1]<c[0]*0.75 and c[2]<c[0]*0.55
    nh=sum(is_hair(c) for c in cs); ns=sum(is_skin(c) for c in cs)
    if nh>0: brown+=1
    if ns>0: skin+=1
    if nh>0 and ns>0:
        ctr=np.mean([P[me.loops[li].vertex_index] for li in poly.loop_indices],axis=0)
        mixed.append((tuple(np.round(ctr,3)), nh, ns))
print("UV 頭より上の面: 髪色を含む %d、肌色を含む %d、両方を含む（境目）%d"%(brown,skin,len(mixed)))
for m in mixed[:10]: print("UV   両方の面 位置%s 髪%d 肌%d"%m)
# 髪の中で肌色を拾っている頂点（周囲が全部髪色なのに自分だけ肌色）
