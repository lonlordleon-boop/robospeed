# -*- coding: utf-8 -*-
"""新しく作り直したテクスチャのうち、頭に使われている画素だけを元のテクスチャへ移す。
   体や靴は元の絵のまま残す。境目は数画素かけて混ぜる。
   実行: blender -b --factory-startup -P mergehead.py -- 入力.glb 元テクスチャ 新テクスチャ 出力 [ぼかし幅]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,OLD,NEW,OUT=a[0],a[1],a[2],a[3]; FEA=int(a[4]) if len(a)>4 else 6
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
neckz=(arm.matrix_world@arm.pose.bones['neck'].head).z
mw=mesh.matrix_world
o1=bpy.data.images.load(OLD); W,H=o1.size
A=np.array(o1.pixels[:],dtype=np.float32).reshape(H,W,4)
n1=bpy.data.images.load(NEW)
if n1.size[0]!=W or n1.size[1]!=H:
    print("MH 大きさが違う: 元 %dx%d 新 %dx%d"%(W,H,n1.size[0],n1.size[1]))
Bn=np.array(n1.pixels[:],dtype=np.float32).reshape(n1.size[1],n1.size[0],4)
if Bn.shape[0]!=H or Bn.shape[1]!=W:
    ys=(np.arange(H)*Bn.shape[0]//H).clip(0,Bn.shape[0]-1)
    xs=(np.arange(W)*Bn.shape[1]//W).clip(0,Bn.shape[1]-1)
    Bn=Bn[ys][:,xs]
uvl=me.uv_layers.active.data
me.calc_loop_triangles()
def raster(tris,mg=0.3):
    m=np.zeros((H,W),bool)
    for t in tris:
        uv=np.array([uvl[li].uv for li in t.loops],float)
        xs=uv[:,0]*W; ys=uv[:,1]*H
        x0=max(0,int(np.floor(xs.min()))-1); x1=min(W-1,int(np.ceil(xs.max()))+1)
        y0=max(0,int(np.floor(ys.min()))-1); y1=min(H-1,int(np.ceil(ys.max()))+1)
        if x1<x0 or y1<y0 or (x1-x0)>500 or (y1-y0)>500: continue
        gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
        dd=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
        if abs(dd)<1e-12: continue
        l1=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/dd
        l2=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/dd
        l3=1-l1-l2
        m[y0:y1+1,x0:x1+1] |= (l1>=-mg)&(l2>=-mg)&(l3>=-mg)
    return m
head=[t for t in me.loop_triangles if (mw@me.polygons[t.polygon_index].center).z>neckz]
body=[t for t in me.loop_triangles if (mw@me.polygons[t.polygon_index].center).z<=neckz]
Mh=raster(head,0.2); Mb=raster(body,0.2)
M=Mh&(~Mb)     # 体と共用している画素は元のまま（服の絵を壊さない）
print("MH 頭の画素 %d、体と共用 %d、入れ替える %d"%(int(Mh.sum()),int((Mh&Mb).sum()),int(M.sum())))
def box(m,rr):
    c=np.cumsum(np.cumsum(np.pad(m.astype(np.float32),((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
    return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
w=np.clip(box(M,FEA),0,1)[:,:,None]
out=A.copy(); out[:,:,:3]=A[:,:,:3]*(1-w)+Bn[:,:,:3]*w
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("MH 書き出し",OUT)
