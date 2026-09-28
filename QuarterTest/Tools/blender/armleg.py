import bpy,sys
a=sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=a[0])
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
act=next(x for x in bpy.data.actions if x.name.startswith(a[1] if len(a)>1 else 'Walk_Child'))
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action=act; f0,f1=act.frame_range; N=int(f1-f0)
rows=[]
for i in range(0,N,2):
    bpy.context.scene.frame_set(int(f0+i)); bpy.context.view_layer.update()
    P=arm.pose.bones; hy=P['Hips'].head.y
    # 前は -y。前へ出ているほど大きい値にする
    rows.append((i, -(P['LeftFoot'].head.y-hy), -(P['LeftHand'].head.y-hy), -(P['RightFoot'].head.y-hy), -(P['RightHand'].head.y-hy)))
import statistics as st
def corr(x,y):
    mx,my=st.mean(x),st.mean(y); return sum((a-mx)*(b-my) for a,b in zip(x,y))/((sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))**0.5)
lf=[r[1] for r in rows]; lh=[r[2] for r in rows]; rf=[r[3] for r in rows]; rh=[r[4] for r in rows]
print("AL 左足と左手の前後の相関 %.2f（－なら逆に動く＝正しい）  右足と右手 %.2f  左足と右手 %.2f"%(corr(lf,lh),corr(rf,rh),corr(lf,rh)))
for r in rows[:7]: print("AL コマ%2d 左足%+6.1f 左手%+6.1f 右足%+6.1f 右手%+6.1f"%r)
