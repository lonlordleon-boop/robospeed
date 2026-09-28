# 指定クリップを N コマ等間隔で、指定の向きから1列に描く（カメラは固定：腰の上下も見える）
import bpy,sys,math,os,numpy as np
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]; SRC,OUT,CLIP,N,AZ=a[0],a[1],a[2],int(a[3]),float(a[4])
F0=float(a[5]) if len(a)>5 else None; F1=float(a[6]) if len(a)>6 else None
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o,do_unlink=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
act=next(ac for ac in bpy.data.actions if ac.name==CLIP or ac.name.startswith(CLIP)); arm.animation_data.action=act
f0,f1=act.frame_range
if F0 is not None: f0,f1=F0,F1
sc=bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH'; sc.display.shading.light='STUDIO'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
me=[o for o in bpy.data.objects if o.type=='MESH'][0]
sc.frame_set(int(f0)); dg=bpy.context.evaluated_depsgraph_get(); em=me.evaluated_get(dg).to_mesh()
P=np.array([tuple(me.matrix_world@v.co) for v in em.vertices]); me.evaluated_get(dg).to_mesh_clear()
H=P[:,2].max()-P[:,2].min(); Z0=P[:,2].min()
CW=300; CH=int(CW*1.5); sc.render.resolution_x=CW; sc.render.resolution_y=CH
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cd.ortho_scale=H*1.5
cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
C=Vector(((P[:,0].min()+P[:,0].max())/2,(P[:,1].min()+P[:,1].max())/2,Z0+H*0.62))
ar=math.radians(AZ); R=10
cam.location=(C.x+R*math.sin(ar),C.y-R*math.cos(ar),C.z); cam.rotation_euler=(C-Vector(cam.location)).to_track_quat('-Z','Y').to_euler()
tmp=os.path.join(os.path.dirname(OUT),"_row"); os.makedirs(tmp,exist_ok=True); tiles=[]
for i in range(N):
    fr=f0+(f1-f0)*i/N; sc.frame_set(int(fr),subframe=fr-int(fr))
    p=os.path.join(tmp,"r_%d.png"%i); sc.render.filepath=p; bpy.ops.render.render(write_still=True); tiles.append(p)
buf=np.ones((CH,CW*N,4),np.float32)
for k,p in enumerate(tiles):
    im=bpy.data.images.load(p); buf[:,k*CW:(k+1)*CW]=np.array(im.pixels[:],np.float32).reshape(CH,CW,4)
sh=bpy.data.images.new("s",CW*N,CH); sh.pixels=buf.ravel(); sh.filepath_raw=OUT; sh.file_format='PNG'; sh.save()
print("ROW",act.name,f0,f1,"H",round(H,3))
