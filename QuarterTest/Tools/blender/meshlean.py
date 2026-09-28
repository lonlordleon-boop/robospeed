# -*- coding: utf-8 -*-
"""骨ではなくメッシュ本体で測る：ポーズ適用後の頂点から、頭・胸・腰の各帯の中心xを、両足の中心x基準で出す。
   （見た目の左右の傾きを、骨の置き方に依存せず測るため）+は左。"""
import bpy, sys
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC = a[0]; CLIPS = a[1].split(',')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
if arm.animation_data is None: arm.animation_data_create()
def verts():
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    v=np.array([tuple(ev.matrix_world @ x.co) for x in me.vertices]); ev.to_mesh_clear(); return v
def row(tag):
    v=verts(); z=v[:,2]; zmin=z.min(); H=z.max()-zmin; n=(z-zmin)/H
    feet=v[n<0.06]; fc=feet[:,0].mean()
    def band(a,b): s=v[(n>=a)&(n<b)]; return s[:,0].mean()-fc
    print("ML %-14s 足中心x%+.3f  腰帯(35-45%%)%+.3f  胸帯(45-58%%)%+.3f  頭帯(65-95%%)%+.3f  頭上端(90-100%%)%+.3f" % (tag, fc, band(.35,.45), band(.45,.58), band(.65,.95), band(.90,1.01)))
arm.animation_data.action=None; bpy.context.view_layer.update(); row("rest")
for c in CLIPS:
    act=bpy.data.actions.get(c); arm.animation_data.action=act; f0,f1=act.frame_range
    for k in range(8):
        bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/8))); bpy.context.view_layer.update(); row("%s %d"%(c,k))
