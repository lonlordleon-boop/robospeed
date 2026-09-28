# -*- coding: utf-8 -*-
"""指定したクリップを「素の姿勢のまま立っているだけ」に差し替える。

   生成された待機アニメは、右手首を左より30度も余計に折っていた（走りも22度折っている）。
   直すより先に、まず立たせておきたいときに使う。クリップ名と長さはそのまま残すので、
   dressup.html のボタンも Unity 側の呼び出しも変えなくていい。

   骨をぜんぶ素の姿勢（位置0・回転なし・大きさ1）に置いて、最初と最後に鍵を打つだけ。
   途中に鍵が無いので、どのフレームでも同じ姿勢になる。

   「腕を下ろす角度」を書くと、そのぶん腕を体へ寄せてから鍵を打つ。
   素の姿勢はA字で腕が開いているので、そのまま立たせると広げすぎに見える。
   骨を回すので服も髪も付いてくるが、このクリップの中だけの話で、歩きや走りには影響しない。
   dressup.html の「腕を広げる」を負の値にしたのと同じ結果になる。

   実行: blender -b --factory-startup -P stillclip.py --
         入力.glb 出力.glb クリップ名 [腕を下ろす角度 既定0]
   例:   ... -- doll.glb out.glb Idle 20
"""
import bpy, sys, os, math
from mathutils import Quaternion, Vector

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, NAME = a[0], a[1], a[2]
DOWN = float(a[3]) if len(a) > 3 else 0.0

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
ad = arm.animation_data
if ad is None:
    print("SC アニメが入っていない"); sys.exit(1)

# 差し替える相手を探す。書き出し後の名前はトラック名ではなくアクション名になる
target = None
for tr in list(ad.nla_tracks):
    for st in tr.strips:
        if st.action and (st.action.name == NAME or st.action.name.startswith(NAME)):
            target = (tr, st, st.action)
print("SC 対象 %s" % (target[2].name if target else "見つからない"))
if target is None:
    print("SC あるクリップ: %s" % [st.action.name for tr in ad.nla_tracks for st in tr.strips])
    sys.exit(1)
tr, st, old = target
f0, f1 = int(old.frame_range[0]), int(old.frame_range[1])
print("SC 長さ %d 〜 %d フレーム" % (f0, f1))

# 骨を素の姿勢に戻す
for pb in arm.pose.bones:
    pb.location = (0.0, 0.0, 0.0)
    pb.scale = (1.0, 1.0, 1.0)
    if pb.rotation_mode == 'QUATERNION': pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    else: pb.rotation_euler = (0.0, 0.0, 0.0)

# 腕を体へ寄せる。回す軸は「前を向く向き」（Head から headfront、上下は捨てる）。
# posebody.py と同じ軸。左腕は負、右腕は正で閉じる
if DOWN:
    def head(n):
        b = arm.data.bones.get(n)
        return (arm.matrix_world @ b.head_local) if b else None
    hd, hf = head('Head'), head('headfront')
    AX = Vector((hf.x - hd.x, hf.y - hd.y, 0.0)) if (hd and hf) else Vector((0.0, -1.0, 0.0))
    AX = AX.normalized() if AX.length > 1e-9 else Vector((0.0, -1.0, 0.0))
    print("SC 前を向く軸 (%.3f, %.3f, %.3f)  腕を %.1f 度 下ろす" % (AX.x, AX.y, AX.z, DOWN))
    for name, sgn in (('LeftArm', -1.0), ('RightArm', +1.0)):
        pb = arm.pose.bones.get(name)
        if pb is None:
            print("SC 骨 %s が無い" % name); continue
        # world の軸を、その骨の素の姿勢での向きに直してから回す
        rest = (arm.matrix_world @ pb.bone.matrix_local).to_quaternion()
        axl = rest.inverted() @ AX
        q = Quaternion(axl, math.radians(DOWN * sgn))
        if pb.rotation_mode == 'QUATERNION': pb.rotation_quaternion = q
        else: pb.rotation_euler = q.to_euler(pb.rotation_mode)
        print("SC %s を %.1f 度 回した" % (name, DOWN * sgn))

act = bpy.data.actions.new(NAME + "_still")
ad.action = act
n = 0
for f in (f0, f1):
    bpy.context.scene.frame_set(f)
    for pb in arm.pose.bones:
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("scale", frame=f)
        if pb.rotation_mode == 'QUATERNION': pb.keyframe_insert("rotation_quaternion", frame=f)
        else: pb.keyframe_insert("rotation_euler", frame=f)
        n += 1
print("SC 鍵を打った骨のべ %d 本" % n)
ad.action = None

# 元のトラックを外して、同じ名前で差し替える。
# 元のアクションもこの場面から外しておく。残したままだと名前がぶつかって
# 新しい方が Idle.001 になり、書き出したクリップ名が変わってしまう（実際なった）。
ad.nla_tracks.remove(tr)
oldname = old.name
bpy.data.actions.remove(old)
act.name = oldname                   # 書き出し後の名前をそろえる
NAME = oldname
nt = ad.nla_tracks.new(); nt.name = NAME
ns = nt.strips.new(NAME, f0, act); ns.name = NAME
print("SC 差し替えた。今のクリップ: %s" % [s.action.name for t in ad.nla_tracks for s in t.strips])

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_animation_mode='NLA_TRACKS',
                          export_skins=True, export_yup=True, export_morph=True,
                          export_image_format='JPEG', export_jpeg_quality=92)
print("SC 書き出し", DST, os.path.getsize(DST))
