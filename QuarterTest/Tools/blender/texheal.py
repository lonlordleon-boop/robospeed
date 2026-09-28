# -*- coding: utf-8 -*-
"""テクスチャの上で、髪の色に囲まれているのに肌色になっている画素を、まわりの髪の色で塗り直す。
   このモデルの髪の房は形ではなく絵で描かれており、その房の途中に肌色の帯が乗っていた。
   広い肌の面（顔そのもの）は、まわりも肌なので対象にならない。
   実行: blender -b --factory-startup -P texheal.py -- 元テクスチャ 出力テクスチャ 半径 髪の割合 [mark]"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,DST=a[0],a[1]; R=int(a[2]) if len(a)>2 else 24; FR=float(a[3]) if len(a)>3 else 0.75
MARK=len(a)>4 and a[4]=='mark'
im=bpy.data.images.load(SRC); W,H=im.size
px=np.array(im.pixels[:],dtype=np.float32).reshape(H,W,4)
r,g,b=px[:,:,0],px[:,:,1],px[:,:,2]
hair=((r>0.28)&(r<0.90)&(g<r*0.75)&(b<r*0.55)).astype(np.float32)
skin=((r>0.66)&(g>0.40)&(b>0.30)&(g<r*0.99)&(b<g*1.10)).astype(np.float32)
def box(m,rr):
    c=np.cumsum(np.cumsum(np.pad(m,((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
    return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
hf=box(hair,R); sf=box(skin,R)
bad=(skin>0)&(hf>=FR)&(sf<(1.0-FR))
print("TH 半径%d・髪%.0f%%以上: 直す画素 %d（全体の %.3f%%）"%(R,100*FR,int(bad.sum()),100*bad.mean()))
# 塗る色＝まわりの髪の画素の平均
out=px.copy()
if bad.sum():
    hsum=np.stack([box(hair*px[:,:,k],R) for k in range(3)],2)
    hcnt=np.maximum(hf,1e-6)
    hcol=hsum/hcnt[:,:,None]
    if MARK:
        out[bad,0]=0; out[bad,1]=1; out[bad,2]=0
    else:
        for k in range(3): out[:,:,k]=np.where(bad, hcol[:,:,k], out[:,:,k])
o=bpy.data.images.new("o",W,H); o.pixels=out.ravel().tolist()
o.filepath_raw=DST; o.file_format='PNG'; o.save(); print("TH 書き出し",DST)
