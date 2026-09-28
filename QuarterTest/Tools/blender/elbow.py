import bpy,sys,math
a=sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=a[0])
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
tr=[(t.name,t.strips[0].action) for t in arm.animation_data.nla_tracks]
for t in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(t)
out=[]
for nm,act in tr:
    arm.animation_data.action=act; f0,f1=map(int,act.frame_range); mx=0; mn=999
    for f in range(f0,f1+1):
        bpy.context.scene.frame_set(f)
        A=arm.pose.bones['LeftArm']; F=arm.pose.bones['LeftForeArm']
        ang=math.degrees((A.tail-A.head).angle(F.tail-F.head)); mx=max(mx,ang); mn=min(mn,ang)
    out.append("%s %.0f〜%.0f度"%(nm,mn,mx))
print("EL ひじの曲がり（左）", " / ".join(out))
