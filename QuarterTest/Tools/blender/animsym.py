import bpy,sys,math
a=sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=a[0])
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
act=next(x for x in bpy.data.actions if x.name.startswith(a[1]))
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action=act; f0,f1=act.frame_range; N=int(f1-f0)
HALF = a[2]=='half'   # 歩き：半周期ずらした反対側と比べる
def dirs(f):
    bpy.context.scene.frame_set(int(f)); bpy.context.view_layer.update()
    out={}
    for s in ('Left','Right'):
        for b in ('Arm','ForeArm','Hand','UpLeg','Leg','Foot'):
            p=arm.pose.bones[s+b]; out[s+b]=(p.tail-p.head).normalized()
    return out
worst={}
for i in range(0,N,max(1,N//12)):
    d=dirs(f0+i); e=dirs(f0+(i+N//2)%N) if HALF else d
    for b in ('Arm','ForeArm','Hand','UpLeg','Leg','Foot'):
        L=d['Left'+b]; R=e['Right'+b].copy(); R.x=-R.x
        ang=math.degrees(L.angle(R)); worst[b]=max(worst.get(b,0),ang)
print("AS",a[1],"左右差の最大（度）",{k:round(v,1) for k,v in worst.items()})
