import bpy,sys
a=sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=a[0])
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
for b in arm.data.bones:
    if b.name.startswith(('Right',)) or 'Hand' in b.name and b.name not in ('LeftHand',): continue
    h=b.head_local; t=b.tail_local
    print("BT %-14s 頭 (%6.1f %6.1f %6.1f)  先 (%6.1f %6.1f %6.1f)  親 %s"%(b.name,h.x,h.y,h.z,t.x,t.y,t.z,b.parent.name if b.parent else '-'))
