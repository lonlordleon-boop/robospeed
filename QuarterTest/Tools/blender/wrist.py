# 手首の曲がり：前腕の向きと手の骨の向きの角度（素の姿勢と、各クリップの最小〜最大）。左右とも
import bpy, sys, math
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]; SRC = a[0]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
P = arm.pose.bones
def wr(s):
    fa = (P[s+'Hand'].head - P[s+'ForeArm'].head).normalized(); h = (P[s+'Hand'].tail - P[s+'Hand'].head).normalized()
    return math.degrees(fa.angle(h))
arm.animation_data.action = None
for pb in P: pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
print("WR 素の姿勢 左 %.1f 右 %.1f" % (wr('Left'), wr('Right')))
for act in bpy.data.actions:
    arm.animation_data.action = act; f0, f1 = map(int, act.frame_range); L = []; R = []
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f); L.append(wr('Left')); R.append(wr('Right'))
    print("WR %-10s 左 %.0f〜%.0f  右 %.0f〜%.0f" % (act.name, min(L), max(L), min(R), max(R)))
