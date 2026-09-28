# -*- coding: utf-8 -*-
"""テクスチャの指定した狭い範囲だけで、片方の色をもう片方へ数画素ぶん広げる。
   絵の境目が数画素ずれているために、髪の房に肌色が乗る／頬に髪色が残る箇所を直す。
   面ごとに塗らないので境目がギザギザにならない。
   実行: blender -b --factory-startup -P localgrow.py -- 元 出力 中心画素x,y 箱の幅 広げる画素 方向
        方向 hair=髪を広げる  skin=肌を広げる"""
import bpy, sys
import numpy as np
a=sys.argv[sys.argv.index("--")+1:]
SRC,DST=a[0],a[1]; cx,cy=map(int,a[2].split(',')); BOX=int(a[3]); GROW=int(a[4]); DIR=a[5]
im=bpy.data.images.load(SRC); W,H=im.size
px=np.array(im.pixels[:],dtype=np.float32).reshape(H,W,4)
x0=max(0,cx-BOX//2); x1=min(W,cx+BOX//2); y0=max(0,cy-BOX//2); y1=min(H,cy+BOX//2)
sub=px[y0:y1,x0:x1].copy()
r,g,b=sub[:,:,0],sub[:,:,1],sub[:,:,2]
hair=(r>0.26)&(r<0.92)&(g<r*0.76)&(b<r*0.58)
skin=(r>0.62)&(g>0.36)&(b>0.26)&(g<r*0.995)&(b<g*1.18)
src,dst=(hair,skin) if DIR=='hair' else (skin,hair)
def box(m,rr):
    c=np.cumsum(np.cumsum(np.pad(m.astype(np.float32),((rr+1,rr),(rr+1,rr)),mode='edge'),0),1)
    return (c[2*rr+1:,2*rr+1:]-c[:-2*rr-1,2*rr+1:]-c[2*rr+1:,:-2*rr-1]+c[:-2*rr-1,:-2*rr-1])/((2*rr+1)**2)
near=box(src,GROW)>0.0
chg=dst&near
# 広げる色＝範囲内の src の色の中央値
col=np.median(sub[:,:,:3][src],0) if src.sum() else np.array([0.5,0.22,0.02])
w=np.clip(box(chg,2),0,1)[:,:,None]     # ふちを少しぼかす
new=sub.copy()
for k in range(3):
    new[:,:,k]=np.where(chg, col[k], sub[:,:,k])
new[:,:,:3]=sub[:,:,:3]*(1-w*0)+new[:,:,:3]*(1)  # 単純置換（境目は元の絵の階調が残る）
px[y0:y1,x0:x1]=new
print("LG 範囲(%d,%d)-(%d,%d) 広げた画素 %d 色 %.2f/%.2f/%.2f"%(x0,y0,x1,y1,int(chg.sum()),*col))
o=bpy.data.images.new("o",W,H); o.pixels=px.ravel().tolist()
o.filepath_raw=DST; o.file_format='PNG'; o.save(); print("LG 書き出し",DST)
