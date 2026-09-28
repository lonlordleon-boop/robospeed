# -*- coding: utf-8 -*-
"""2つの GLB を同じ角度・同じコマで描き、上下に並べる（違いを見つけるため）。
   実行: blender -b --factory-startup -P diffshot.py -- A.glb B.glb 出力.png クリップ コマ数 方位角,仰角"""
import bpy, sys, math, os
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]
A,Bg,OUT,CLIP=a[0],a[1],a[2],a[3]; N=int(a[4]); AZ,EL=map(float,a[5].split(','))
CW,CH=300,420
def shots(path,tag):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    for o in list(bpy.data.objects):
        if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
    arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    if arm.animation_data is None: arm.animation_data_create()
    act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
    sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'
    sc.display.shading.light='FLAT'; sc.display.shading.color_type='TEXTURE'
    sc.world=bpy.data.worlds.new("w"); sc.world.use_nodes=False; sc.world.color=(1,1,1)
    sc.render.resolution_x=CW; sc.render.resolution_y=CH; sc.render.image_settings.file_format='PNG'
    cd=bpy.data.cameras.new("c"); cd.type='ORTHO'; cam=bpy.data.objects.new("c",cd); sc.collection.objects.link(cam); sc.camera=cam
    aw=arm.matrix_world
    sc.frame_set(int(f0)); bpy.context.view_layer.update()
    top=(aw@arm.pose.bones["head_end"].head).z; low=min((aw@arm.pose.bones[n].head).z for n in ("LeftToeBase","RightToeBase"))
    Hh=(top-low); cd.ortho_scale=Hh*1.15
    out=[]
    tmp=os.path.join(os.path.dirname(OUT),"_d"); os.makedirs(tmp,exist_ok=True)
    for k in range(N):
        sc.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
        hp=aw@arm.pose.bones["Hips"].head
        c=Vector((hp.x,hp.y,(top+low)/2))
        er,ar=math.radians(EL),math.radians(AZ); R=20
        cam.location=(c.x+R*math.cos(er)*math.sin(ar), c.y-R*math.cos(er)*math.cos(ar), c.z+R*math.sin(er))
        cam.rotation_euler=(c-Vector(cam.location)).to_track_quat('-Z','Y').to_euler()
        p=os.path.join(tmp,"%s_%d.png"%(tag,k)); sc.render.filepath=p; bpy.ops.render.render(write_still=True); out.append(p)
    return out
pa=shots(A,'a'); pb=shots(Bg,'b')
W=CW*N; H=CH*2; sh=bpy.data.images.new("s",W,H); buf=[1.0]*(W*H*4)
for row,ps in ((1,pa),(0,pb)):
    for i,p in enumerate(ps):
        im=bpy.data.images.load(p); px=im.pixels[:]
        for y in range(CH):
            d=((row*CH+y)*W+i*CW)*4; buf[d:d+CW*4]=px[y*CW*4:(y+1)*CW*4]
        bpy.data.images.remove(im)
sh.pixels=buf; sh.filepath_raw=OUT; sh.file_format='PNG'; sh.save(); print("DF",OUT)
