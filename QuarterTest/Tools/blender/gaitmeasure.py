# クリップの各コマで、骨の向きを「真横から見た角度」で測る（0=真下、＋=前へ（−y 方向）振れる）。高さは身長比
import bpy,sys,math
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]; SRC,CLIP=a[0],a[1]; N=int(a[2]) if len(a)>2 else 0
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
act=next(ac for ac in bpy.data.actions if ac.name==CLIP or ac.name.startswith(CLIP)); arm.animation_data.action=act
f0,f1=act.frame_range; sc=bpy.context.scene; MW=arm.matrix_world
def P(n,t=False):
    pb=arm.pose.bones[n]; return MW@(pb.tail if t else pb.head)
# 身長の目安：素の姿勢の頭の先〜足首
Hn=None
def ang(v):  # 真横（y-z 面）での角度。0=真下、＋=前（−y）
    return math.degrees(math.atan2(-v.y,-v.z))
def ang_up(v): return math.degrees(math.atan2(-v.y,v.z))  # 上向きの骨：0=真上、＋=前へ倒れる
rows=[]
nf=int(f1-f0) if N==0 else N
for i in range(nf+1):
    fr=f0+(f1-f0)*i/nf; sc.frame_set(int(fr),subframe=fr-int(fr))
    hd=P('Head',True).z; fz=min(P('LeftFoot').z,P('RightFoot').z)
    if Hn is None: Hn=hd-fz
    r=dict(f=round(fr,1))
    r['hipZ']=P('Hips').z/Hn*100
    r['lean']=ang_up(P('neck')-P('Hips'))
    for s in ('Left','Right'):
        k=s[0]
        r[k+'thigh']=ang(P(s+'Leg')-P(s+'UpLeg'))
        r[k+'shin']=ang(P(s+'Foot')-P(s+'Leg'))
        r[k+'knee']=r[k+'thigh']-r[k+'shin']
        r[k+'footZ']=(P(s+'Foot').z)/Hn*100
        r[k+'footY']=-(P(s+'Foot').y-P('Hips').y)/Hn*100
        r[k+'arm']=ang(P(s+'ForeArm')-P(s+'Arm'))
        r[k+'fore']=ang(P(s+'Hand')-P(s+'ForeArm'))
        u=(P(s+'ForeArm')-P(s+'Arm')).normalized(); v=(P(s+'Hand')-P(s+'ForeArm')).normalized()
        r[k+'elb']=math.degrees(u.angle(v))
    rows.append(r)
keys=['f','hipZ','lean','Lthigh','Lshin','Lknee','LfootZ','LfootY','Larm','Lelb','Rthigh','Rknee','RfootZ','Rarm','Relb']
print("GM "+" ".join("%7s"%k for k in keys))
for r in rows: print("GM "+" ".join("%7.1f"%r[k] for k in keys))
print("GM range "+" ".join("%7.1f"%(max(r[k] for r in rows)-min(r[k] for r in rows)) for k in keys))
print("GM min   "+" ".join("%7.1f"%min(r[k] for r in rows) for k in keys))
print("GM max   "+" ".join("%7.1f"%max(r[k] for r in rows) for k in keys))
print("GM Hn",round(Hn,3),"frames",f0,f1)
