# -*- coding: utf-8 -*-
"""髪のポリゴンなのに肌の色を拾っている面を見つけ、その面が使うテクスチャの画素を
   まわりの髪の色で塗り直す（Meshy のテクスチャ焼き付けで、耳や生え際の肌色が
   隣の髪の島へはみ出しているため）。
   耳そのもの（広い肌の領域）は塗らないよう、肌の面が小さなかたまりの場合だけ直す。
   実行: blender -b --factory-startup -P bleedfix.py -- 入力.glb 元テクスチャ 出力テクスチャ [mark]
        mark を付けると、直す場所を緑で塗って確認できる。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]; MARK=len(a)>3 and a[3]=='mark'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
neckz=(arm.matrix_world@arm.pose.bones['neck'].head).z
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
NF=len(me.polygons); col=np.zeros((NF,3)); ctr=np.zeros((NF,3))
for f in me.polygons:
    uv=np.array([uvl[li].uv for li in f.loop_indices])
    cs=[px[int(np.clip(u[1],0,.9999)*H),int(np.clip(u[0],0,.9999)*W),:3] for u in uv]
    col[f.index]=np.mean(cs,0)
    ctr[f.index]=np.mean([tuple(mesh.matrix_world@me.vertices[me.loops[li].vertex_index].co) for li in f.loop_indices],0)
def cls(c):
    r,g,b=c
    if r>0.68 and g>0.42 and b>0.32 and g<r*0.99 and b<g*1.08: return 1
    if r>0.28 and g<r*0.75 and b<r*0.55: return 2
    return 0
K=np.array([cls(c) for c in col])
e2f={}
for f in me.polygons:
    for e in f.edge_keys: e2f.setdefault(e,[]).append(f.index)
nb=[[] for _ in range(NF)]
for f in me.polygons:
    for e in f.edge_keys: nb[f.index]+=[j for j in e2f.get(e,[]) if j!=f.index]
nb2=[list(set(sum([nb[j] for j in nb[i]],[])+nb[i])-{i}) for i in range(NF)]
cand=[]
for i in range(NF):
    if K[i]!=1 or ctr[i][2] < neckz: continue      # 首より下は対象外（靴などの誤検出を避ける）
    n=[K[j] for j in nb2[i]]
    if n and n.count(2)/len(n) >= 0.5: cand.append(i)
# 肌の面のつながりで、かたまりの大きさを見る（耳のような広い肌は除く）
skin=set(i for i in range(NF) if K[i]==1)
par={i:i for i in skin}
def find(x):
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
for i in skin:
    for j in nb[i]:
        if j in skin: par[find(i)]=find(j)
size={}
for i in skin: size[find(i)]=size.get(find(i),0)+1
bad=[i for i in cand if size[find(i)]<=40]
print("BF 肌色で髪に囲まれた面 %d、そのうち小さなかたまり（40面以下）%d を直す"%(len(cand),len(bad)))
# 直す色＝2つ隣までの髪の面の色の中央値
fill={}
for i in bad:
    hs=[col[j] for j in nb2[i] if K[j]==2]
    fill[i]=np.median(np.array(hs),0) if hs else np.array([0.45,0.22,0.06])
# 塗る画素をラスタ化（他の面が使っている画素は避ける）
me.calc_loop_triangles()
tri_of=[[] for _ in range(NF)]
for t in me.loop_triangles: tri_of[t.polygon_index].append(t)
def raster(tris):
    m=np.zeros((H,W),bool)
    for t in tris:
        uv=np.array([uvl[li].uv for li in t.loops],float)
        xs=uv[:,0]*W; ys=uv[:,1]*H
        x0=max(0,int(np.floor(xs.min()))-1); x1=min(W-1,int(np.ceil(xs.max()))+1)
        y0=max(0,int(np.floor(ys.min()))-1); y1=min(H-1,int(np.ceil(ys.max()))+1)
        if x1<x0 or y1<y0 or (x1-x0)>300 or (y1-y0)>300: continue
        gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
        d=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(d)<1e-12: continue
        l1=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/d
        l2=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/d
        l3=1-l1-l2
        m[y0:y1+1,x0:x1+1] |= (l1>=-0.3)&(l2>=-0.3)&(l3>=-0.3)
    return m
others=raster([t for i in range(NF) if i not in set(bad) for t in tri_of[i]])
out=px.copy(); painted=0
for i in bad:
    m=raster(tri_of[i]) & (~others)
    c=[0,1,0] if MARK else fill[i]
    out[m,0]=c[0]; out[m,1]=c[1]; out[m,2]=c[2]; painted+=int(m.sum())
print("BF 塗り直した画素 %d"%painted)
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("BF 書き出し",OUT)
