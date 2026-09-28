# -*- coding: utf-8 -*-
"""テクスチャの中で「周りが一色なのに自分だけ浮いている」画素のかたまりを探す（塗りの事故を見つける）。"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]; TEX=a[0]
img=bpy.data.images.load(TEX); W,H=img.size
px=np.array(img.pixels[:],dtype=np.float32).reshape(H,W,4)[:,:,:3]
print("TX 大きさ %dx%d"%(W,H))
def box(a,r):
    c=np.cumsum(np.cumsum(np.pad(a,((r+1,r),(r+1,r)),mode='edge'),0),1)
    s=c[2*r+1:,2*r+1:]-c[:-2*r-1,2*r+1:]-c[2*r+1:,:-2*r-1]+c[:-2*r-1,:-2*r-1]
    return s/((2*r+1)**2)
r,g,b=px[:,:,0],px[:,:,1],px[:,:,2]
hair=((r>0.30)&(r<0.85)&(g<r*0.72)&(b<r*0.52)).astype(np.float32)
skin=((r>0.70)&(g>0.48)&(b>0.38)&(g<r*0.99)&(b<g*1.02)).astype(np.float32)
print("TX 髪色の画素 %.1f%%  肌色の画素 %.1f%%"%(100*hair.mean(),100*skin.mean()))
for R in (24,48):
    hf=box(hair,R)
    bad=(skin>0)&(hf>0.80)
    print("TX 半径%d: 髪に囲まれた肌色の画素 %d 個"%(R,bad.sum()))
    if bad.sum():
        ys,xs=np.where(bad)
        # かたまりに分ける（粗く：32画素の格子でまとめる）
        cell={}
        for y,x in zip(ys,xs): cell.setdefault((y//64,x//64),0); cell[(y//64,x//64)]+=1
        top=sorted(cell.items(),key=lambda kv:-kv[1])[:8]
        for (cy,cx),n in top: print("TX    %5d画素  UV(%.3f,%.3f) 付近"%(n,(cx*64+32)/W,(cy*64+32)/H))
