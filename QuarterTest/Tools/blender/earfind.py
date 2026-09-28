# -*- coding: utf-8 -*-
"""耳を形から切り出す。頭の表面をならした形と比べ、外へ張り出している面を耳とみなす。
   （このモデルは頭がひと繋がりの塊で、髪と肌の境目は塗りにしか無いため、耳だけは形で拾う）"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]; TH=float(a[1]) if len(a)>1 else 0.004
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
neckz=(arm.matrix_world@arm.pose.bones['neck'].head).z
mw=mesh.matrix_world
P=np.array([tuple(mw@v.co) for v in me.vertices]); nv=len(P)
N=np.array([tuple((mw.to_3x3()@v.normal).normalized()) for v in me.vertices])
# 同じ位置の頂点をまとめてから隣を作る（UVの継ぎ目で分かれているため）
key={}; rep=np.arange(nv)
for v in range(nv):
    k=tuple(np.round(P[v],5))
    if k in key: rep[v]=key[k]
    else: key[k]=v
nb=[[] for _ in range(nv)]
for e in me.edges:
    a_,b_=rep[e.vertices[0]],rep[e.vertices[1]]
    nb[a_].append(b_); nb[b_].append(a_)
head=P[:,2]>neckz
Q=P.copy()
for _ in range(40):
    Q2=Q.copy()
    for v in range(nv):
        if not head[v] or rep[v]!=v or not nb[v]: continue
        Q2[v]=0.5*Q[v]+0.5*Q[nb[v]].mean(0)
    Q=Q2
for v in range(nv):
    if rep[v]!=v: Q[v]=Q[rep[v]]
pro=((P-Q)*N).sum(1)
print("EF 張り出し量 頭の頂点: 中央値%.4f 最大%.4f"%(np.median(pro[head]),pro[head].max()))
sel=head&(pro>TH)&(np.abs(P[:,0])>0.10)
print("EF 張り出し%.3f超で横にある頂点 %d"%(TH,sel.sum()))
for s in (1,-1):
    m=sel&(np.sign(P[:,0])==s)
    if m.sum()<5: continue
    p=P[m]
    print("EF   x%s側 %d頂点 x %.3f..%.3f y %.3f..%.3f z %.3f..%.3f"%('+' if s>0 else '-',m.sum(),p[:,0].min(),p[:,0].max(),p[:,1].min(),p[:,1].max(),p[:,2].min(),p[:,2].max()))
