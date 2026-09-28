# -*- coding: utf-8 -*-
"""足元のアップを、骨の位置に印（球）を置いて描く。列＝正面/後ろ/横、行＝時刻。
   実行: blender -b --factory-startup -P feetshot.py -- 入力.glb 出力.png クリップ 時刻1,時刻2"""
import bpy, sys, math, os
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
SRC, OUT, CLIP = a[0], a[1], a[2]; FRACS=[float(x) for x in a[3].split(',')]
VIEWS=[("front",0,8),("top",0,80),("side",90,8)]; CW,CH=360,300
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
act=bpy.data.actions.get(CLIP)
if arm.animation_data is None: arm.animation_data_create()
arm.animation_data.action=act; f0,f1=act.frame_range
sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'; sc.display.shading.light='FLAT'; sc.display.shading.color_type='TEXTURE'
sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
sc.render.resolution_x=CW; sc.render.resolution_y=CH; sc.render.image_settings.file_format='PNG'
cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
aw=arm.matrix_world
marks={}
mat=bpy.data.materials.new("m"); mat.diffuse_color=(0,1,0,1)
for n in ("LeftLeg","LeftFoot","LeftToeBase","RightLeg","RightFoot","RightToeBase"):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.012); o=bpy.context.active_object; o.name="mark_"+n; o.data.materials.append(mat); marks[n]=o
sc.display.shading.color_type='TEXTURE'
tiles=[]; tmp=os.path.join(os.path.dirname(OUT),"_tiles"); os.makedirs(tmp,exist_ok=True)
for fi,fr in enumerate(FRACS):
    sc.frame_set(int(round(f0+(f1-f0)*fr))); bpy.context.view_layer.update()
    for n,o in marks.items(): o.location=aw@arm.pose.bones[n].head
    hp=aw@arm.pose.bones["Hips"].head
    c=Vector((hp.x,hp.y,0.12)); cd.ortho_scale=0.42
    for vi,(vn,az,el) in enumerate(VIEWS):
        er,ar=math.radians(el),math.radians(az); R=20
        cam.location=(c.x+R*math.cos(er)*math.sin(ar), c.y-R*math.cos(er)*math.cos(ar), c.z+R*math.sin(er))
        cam.rotation_euler=(c-cam.location).to_track_quat('-Z','Y').to_euler()
        p=os.path.join(tmp,"f_%d_%d.png"%(fi,vi)); sc.render.filepath=p; bpy.ops.render.render(write_still=True); tiles.append((fi,vi,p))
W=CW*len(VIEWS); Hh=CH*len(FRACS); sheet=bpy.data.images.new("s",W,Hh); buf=[1.0]*(W*Hh*4)
for fi,vi,p in tiles:
    im=bpy.data.images.load(p); px=im.pixels[:]
    for y in range(CH):
        d=((Hh-1-(fi*CH+(CH-1-y)))*W+vi*CW)*4; buf[d:d+CW*4]=px[y*CW*4:(y+1)*CW*4]
    bpy.data.images.remove(im)
sheet.pixels=buf; sheet.filepath_raw=OUT; sheet.file_format='PNG'; sheet.save(); print("FEET",OUT)
