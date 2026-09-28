# -*- coding: utf-8 -*-
"""テクスチャの一部を切り出して1枚に並べる（確認用）。引数: テクスチャ 出力 u,v u,v ... 切り出し幅"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; TEX,OUT=a[0],a[1]; UVS=[tuple(map(float,s.split(','))) for s in a[2].split(';')]; SZ=int(a[3]) if len(a)>3 else 256
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)
n=len(UVS); out=np.ones((SZ,SZ*n,4),np.float32)
for i,(u,v) in enumerate(UVS):
    cx=int(u*W); cy=int(v*H); x0=max(0,min(W-SZ,cx-SZ//2)); y0=max(0,min(H-SZ,cy-SZ//2))
    out[:,i*SZ:(i+1)*SZ]=px[y0:y0+SZ,x0:x0+SZ]
im=bpy.data.images.new("c",SZ*n,SZ); im.pixels=out.ravel().tolist()
im.filepath_raw=OUT; im.file_format='PNG'; im.save(); print("CR",OUT)
