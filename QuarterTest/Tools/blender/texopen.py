# -*- coding: utf-8 -*-
"""テクスチャ上で、肌色の領域が髪の領域へ細く食い込んでいる部分（出っ張り）を削り、髪の色に戻す。
   髪の房は形ではなく絵で描かれているので、房の上に肌色が乗ると髪に肌色が混じって見える。
   出っ張りだけを消す処理（収縮→膨張）を使うので、顔そのものの輪郭は残る。
   実行: blender -b --factory-startup -P texopen.py -- 元テクスチャ 出力テクスチャ 半径 [mark]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,DST=a[0],a[1]; R=int(a[2]) if len(a)>2 else 20; MARK=len(a)>3 and a[3]=='mark'
im=bpy.data.images.load(SRC); W,H=im.size
px=np.array(im.pixels[:],dtype=np.float32).reshape(H,W,4)
r,g,b=px[:,:,0],px[:,:,1],px[:,:,2]
hair=((r>0.28)&(r<0.90)&(g<r*0.75)&(b<r*0.55))
skin=((r>0.66)&(g>0.40)&(b>0.30)&(g<r*0.99)&(b<g*1.10))
def box(m,rr):
    c=np.cumsum(np.cumsum(np.pad(m.astype(np.float32),((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
    return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
ero=box(skin,R)>0.999
opened=box(ero,R)>0.0
# 削られた肌色の画素のうち、まわりに髪があるものだけを直す（背景側は触らない）
bad=skin&(~opened)&(box(hair,R)>0.15)
print("TO 半径%d: 肌色の出っ張り %d 画素（全体の %.3f%%）"%(R,int(bad.sum()),100*bad.mean()))
out=px.copy()
if bad.sum():
    hs=np.stack([box(hair*px[:,:,k],R*2) for k in range(3)],2); hc=np.maximum(box(hair,R*2),1e-6)
    col=hs/hc[:,:,None]
    if MARK:
        out[bad,0]=0; out[bad,1]=1; out[bad,2]=0
    else:
        for k in range(3): out[:,:,k]=np.where(bad,col[:,:,k],out[:,:,k])
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=DST; o.file_format='PNG'; o.save(); print("TO 書き出し",DST)
