# 2枚の三面図の前向き（左の x0〜x1）を同じ縮尺で横に並べ、50画素ごとに横線を引く
import bpy,sys,numpy as np
a=sys.argv[sys.argv.index("--")+1:]; OUT=a[0]; x0,x1=int(a[1]),int(a[2]); srcs=a[3:]
tiles=[]
for s in srcs:
    im=bpy.data.images.load(s); W,H=im.size; px=np.array(im.pixels[:],np.float32).reshape(H,W,4)
    tiles.append(px[:, x0:x1])
buf=np.concatenate(tiles,1)
H=buf.shape[0]
for y in range(0,H,50): buf[y,:,:3]=np.where((H-1-y)%250==0, 0.9, 0.55)*np.array([1,0.3,0.3]) if False else buf[y,:,:3]*0.5+np.array([0.5,0,0])*0.5
o=bpy.data.images.new("o",buf.shape[1],H,alpha=True); o.pixels=buf.ravel(); o.filepath_raw=OUT; o.file_format='PNG'; o.save()
