# -*- coding: utf-8 -*-
"""UV の島（テクスチャ上でひと続きの区画）ごとに、塗られている色の内訳を出す。
   髪の房の島に肌色が混ざっていれば、そこが塗りの事故。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,TEX=a[0],a[1]
TARGET=[float(x) for x in a[2].split(',')] if len(a)>2 else None
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
mw=mesh.matrix_world
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
NF=len(me.polygons); col=np.zeros((NF,3)); ctr=np.zeros((NF,3))
for f in me.polygons:
    uv=np.array([uvl[li].uv for li in f.loop_indices])
    col[f.index]=np.mean([px[int(np.clip(u[1],0,.9999)*H),int(np.clip(u[0],0,.9999)*W),:3] for u in uv],0)
    ctr[f.index]=tuple(mw@f.center)
def cls(c):
    r,g,b=c
    if r>0.68 and g>0.42 and b>0.32 and g<r*0.99 and b<g*1.08: return 1
    if r>0.28 and g<r*0.75 and b<r*0.55: return 2
    return 0
K=np.array([cls(c) for c in col])
# UV の島＝UV 座標が一致する角どうしで面をつなぐ
par=list(range(NF))
def find(x):
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
corner={}
for f in me.polygons:
    for li in f.loop_indices:
        k=(round(uvl[li].uv[0],6),round(uvl[li].uv[1],6))
        if k in corner: par[find(f.index)]=find(corner[k])
        else: corner[k]=f.index
isl={}
for i in range(NF): isl.setdefault(find(i),[]).append(i)
print("UI UVの島 %d 個"%len(isl))
rows=[]
for r,fs in isl.items():
    ks=[K[i] for i in fs]; rows.append((len(fs),ks.count(1),ks.count(2),ks.count(0),np.mean(ctr[fs],0),r))
rows.sort(key=lambda x:-x[0])
for n,s,h,o,c,r in rows[:10]:
    print("UI   %5d面 肌%4d 髪%4d 他%4d 中心(%.2f,%.2f,%.2f)"%(n,s,h,o,*c))
if TARGET:
    t=np.array(TARGET); d=np.linalg.norm(ctr-t,axis=1); i=int(np.argmin(d))
    r=find(i); fs=isl[r]; ks=[K[j] for j in fs]
    print("UI 指定位置に一番近い面 %d の島: %d面 肌%d 髪%d 他%d 中心(%.2f,%.2f,%.2f)"%(i,len(fs),ks.count(1),ks.count(2),ks.count(0),*np.mean(ctr[fs],0)))
    p=ctr[fs]
    print("UI   その島の広がり x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f"%(p[:,0].min(),p[:,0].max(),p[:,1].min(),p[:,1].max(),p[:,2].min(),p[:,2].max()))
