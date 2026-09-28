# -*- coding: utf-8 -*-
"""テクスチャの一部を拡大して、10画素ごとの目盛りを重ねて表示する（塗る範囲を決めるため）。
   実行: blender -b --factory-startup -P texzoom.py -- テクスチャ 出力.png u,v 幅(画素) 倍率"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
TEX,OUT=a[0],a[1]; u,v=map(float,a[2].split(',')); SZ=int(a[3]); MAG=int(a[4])
im=bpy.data.images.load(TEX); W,H=im.size
px=np.array(im.pixels[:],dtype=np.float32).reshape(H,W,4)
cx=int(u*W); cy=int(v*H); x0=max(0,cx-SZ//2); y0=max(0,cy-SZ//2)
sub=px[y0:y0+SZ, x0:x0+SZ].copy()
big=np.repeat(np.repeat(sub,MAG,axis=0),MAG,axis=1)
for k in range(0,SZ+1,10):
    p=k*MAG
    if p<big.shape[0]: big[p:p+1,:,:3]=[0,0,1]
    if p<big.shape[1]: big[:,p:p+1,:3]=[0,0,1]
o=bpy.data.images.new("o",SZ*MAG,SZ*MAG); o.pixels=big.ravel().tolist()
o.filepath_raw=OUT; o.file_format='PNG'; o.save()
print("TZ 左下の画素 (%d,%d)  幅 %d画素  1目盛=10画素"%(x0,y0,SZ))
