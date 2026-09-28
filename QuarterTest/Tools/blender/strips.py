import bpy,sys
a=sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=a[0])
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
for t in arm.animation_data.nla_tracks:
    s=t.strips[0]; print("ST",t.name,"strip",s.frame_start,s.frame_end,"action",tuple(s.action.frame_range))
