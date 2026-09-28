# -*- coding: utf-8 -*-
"""Unity の既定のテクスチャ圧縮（4×4画素を2色の間の4段階で表す方式）をまねて、色の混ざりを再現する。
   実行: blender -b --factory-startup -P dxtsim.py -- 入力.png 出力.png"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,DST=a[0],a[1]
im=bpy.data.images.load(SRC); W,H=im.size
px=np.array(im.pixels[:],dtype=np.float32).reshape(H,W,4)
rgb=px[:,:,:3]
bh,bw=H//4,W//4
blk=rgb.reshape(bh,4,bw,4,3).transpose(0,2,1,3,4).reshape(bh,bw,16,3)
mean=blk.mean(2,keepdims=True); d=blk-mean
# 主軸（各ブロックで色が一番ばらけている向き）
u=d[:,:,0,:].copy()
for _ in range(6):
    w=(d*u[:,:,None,:]).sum(-1)          # 射影
    u=(d*w[:,:,:,None]).sum(2)
    n=np.linalg.norm(u,axis=-1,keepdims=True); u=u/np.where(n<1e-8,1,n)
w=(d*u[:,:,None,:]).sum(-1)
c0=mean[:,:,0,:]+u*w.max(2)[:,:,None]
c1=mean[:,:,0,:]+u*w.min(2)[:,:,None]
# 4段階に丸める
t=(w-w.min(2,keepdims=True))/np.maximum(w.max(2,keepdims=True)-w.min(2,keepdims=True),1e-8)
t=np.round(t*3)/3
out=c1[:,:,None,:]+(c0-c1)[:,:,None,:]*t[:,:,:,None]
# 5:6:5 の色数に丸める
out=np.round(np.clip(out,0,1)*np.array([31,63,31]))/np.array([31,63,31])
out=out.reshape(bh,bw,4,4,3).transpose(0,2,1,3,4).reshape(H,W,3)
res=px.copy(); res[:,:,:3]=out
o=bpy.data.images.new("o",W,H); o.pixels=res.ravel().tolist()
o.filepath_raw=DST; o.file_format='PNG'; o.save(); print("DX",DST)
