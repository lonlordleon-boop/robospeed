# -*- coding: utf-8 -*-
"""テクスチャの「島」の外側を、その島の色で塗り広げる（ふちどり／パディング）。
   UV の島どうしが隙間なく詰まっていると、Unity の縮小表示（ミップマップ）や圧縮で
   隣の島の色（肌）が髪の中へにじむ。島の外側だけを自分の色で埋めれば、にじむ相手が自分になる。
   面が使っている画素は一切変えない。
   実行: blender -b --factory-startup -P texpad.py -- 入力.glb 元テクスチャ 出力テクスチャ [広げる画素数]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,TEX,OUT=a[0],a[1],a[2]; PAD=int(a[3]) if len(a)>3 else 16
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH'); me=mesh.data
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
uvl=me.uv_layers.active.data
cov=np.zeros((H,W),bool)
me.calc_loop_triangles()
for t in me.loop_triangles:
    uv=np.array([uvl[li].uv for li in t.loops],dtype=np.float64)
    xs=uv[:,0]*W; ys=uv[:,1]*H
    x0=max(0,int(np.floor(xs.min()))-1); x1=min(W-1,int(np.ceil(xs.max()))+1)
    y0=max(0,int(np.floor(ys.min()))-1); y1=min(H-1,int(np.ceil(ys.max()))+1)
    if x1<x0 or y1<y0: continue
    if (x1-x0)>200 or (y1-y0)>200: continue
    gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
    d=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
    if abs(d)<1e-12: continue
    l1=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/d
    l2=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/d
    l3=1-l1-l2
    m=(l1>=-0.02)&(l2>=-0.02)&(l3>=-0.02)
    cov[y0:y1+1,x0:x1+1] |= m
print("PD 面が使っている画素 %.1f%%（%d 個）"%(100*cov.mean(),cov.sum()))
# 使われていない画素のうち、島のすぐ外（8画素以内）で色が食い違うものを数える
near=cov.copy()
for _ in range(8):
    n=near.copy()
    n[1:,:]|=near[:-1,:]; n[:-1,:]|=near[1:,:]; n[:,1:]|=near[:,:-1]; n[:,:-1]|=near[:,1:]
    near=n
edge=near&(~cov)
print("PD 島のすぐ外の画素 %d 個"%edge.sum())
# 塗り広げ：使われていない画素を、隣の「決まった色」で順に埋める
outpx=px.copy(); known=cov.copy()
for step in range(PAD):
    src=np.zeros((H,W,4),np.float32); cnt=np.zeros((H,W),np.float32)
    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
        sh=np.roll(np.roll(outpx,dy,axis=0),dx,axis=1)
        kn=np.roll(np.roll(known,dy,axis=0),dx,axis=1).astype(np.float32)
        src+=sh*kn[:,:,None]; cnt+=kn
    fill=(~known)&(cnt>0)
    outpx[fill]=(src[fill]/cnt[fill][:,None])
    known|=fill
    if not fill.any(): break
outpx[cov]=px[cov]   # 面が使っている画素は元のまま
d=np.abs(outpx[edge]-px[edge]).mean()
print("PD 塗り広げ %d 画素分。島の外で色が変わった量 平均 %.3f"%(PAD,d))
o=bpy.data.images.new("o",W,H); o.pixels=outpx.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("PD 書き出し",OUT)
