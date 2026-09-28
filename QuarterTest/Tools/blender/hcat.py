import bpy,sys,numpy as np
a=sys.argv[sys.argv.index("--")+1:]; OUT=a[0]; ims=[bpy.data.images.load(p) for p in a[1:]]
W=sum(i.size[0] for i in ims); H=max(i.size[1] for i in ims); buf=np.ones((H,W,4),np.float32); x=0
for i in ims:
    w,h=i.size; buf[H-h:,x:x+w]=np.array(i.pixels[:],np.float32).reshape(h,w,4); x+=w
s=bpy.data.images.new("s",W,H); s.pixels=buf.ravel(); s.filepath_raw=OUT; s.file_format='PNG'; s.save()
