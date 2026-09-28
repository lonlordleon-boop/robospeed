import bpy,sys,numpy as np
a=sys.argv[sys.argv.index("--")+1:]; SRC,OUT=a[0],a[1]; x0,x1,y0,y1=map(int,a[2:6])  # 左上原点の画素
im=bpy.data.images.load(SRC); W,H=im.size; px=np.array(im.pixels[:],np.float32).reshape(H,W,4)[::-1]
c=px[y0:y1,x0:x1][::-1].copy(); h,w=c.shape[:2]
o=bpy.data.images.new("c",w,h,alpha=True); o.pixels=c.ravel(); o.filepath_raw=OUT; o.file_format='PNG'; o.save(); print("CROP",w,h)
