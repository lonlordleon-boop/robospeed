# -*- coding: utf-8 -*-
"""髪の中に紛れ込んだ肌色の面（周りが全部髪色なのに自分だけ肌色）を探す。テクスチャの貼り間違いの検出。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC, TEX = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh = next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
arm  = next(o for o in bpy.data.objects if o.type=='ARMATURE')
img = bpy.data.images.load(TEX); W,Hh = img.size
px = np.array(img.pixels[:]).reshape(Hh,W,4)
uvl = me.uv_layers.active.data
P=np.array([tuple(mesh.matrix_world @ v.co) for v in me.vertices])
headz=(arm.matrix_world@arm.pose.bones['Head'].head).z
def col(uv):
    x=int(np.clip(uv[0],0,0.9999)*W); y=int(np.clip(uv[1],0,0.9999)*Hh)
    return px[y,x,:3]
NF=len(me.polygons)
avg=np.zeros((NF,3)); ctr=np.zeros((NF,3)); above=np.zeros(NF,bool)
for f in me.polygons:
    cs=np.array([col(uvl[li].uv) for li in f.loop_indices]); avg[f.index]=cs.mean(0)
    pts=np.array([P[me.loops[li].vertex_index] for li in f.loop_indices]); ctr[f.index]=pts.mean(0)
    above[f.index]= pts[:,2].mean()>headz
def cls(c):
    if c[0]>0.30 and c[1]<c[0]*0.72 and c[2]<c[0]*0.52: return 'hair'
    if c[0]>0.72 and c[1]>0.50 and c[2]>0.40 and c[1]<c[0]*0.98: return 'skin'
    return 'other'
K=np.array([cls(c) for c in avg])
# 面の隣り（辺を共有）
e2f={}
for f in me.polygons:
    for e in f.edge_keys: e2f.setdefault(e,[]).append(f.index)
bad=[]
for i in range(NF):
    if not above[i] or K[i]!='skin': continue
    nb=[]
    for e in me.polygons[i].edge_keys: nb+= [j for j in e2f.get(e,[]) if j!=i]
    if len(nb)>=2 and all(K[j]=='hair' for j in nb): bad.append(i)
print("IS 頭より上の面 %d、髪に囲まれた肌色の面 %d"%(above.sum(),len(bad)))
if bad:
    c=ctr[bad]
    # 近い場所をまとめる
    used=np.zeros(len(bad),bool); groups=[]
    for i in range(len(bad)):
        if used[i]: continue
        d=np.linalg.norm(c-c[i],axis=1); m=(d<0.03)&(~used); used|=m; groups.append((m.sum(),c[m].mean(0)))
    groups.sort(reverse=True,key=lambda x:x[0])
    for n,p in groups[:8]: print("IS   %d面のかたまり 位置(%.3f,%.3f,%.3f)"%(n,*p))
