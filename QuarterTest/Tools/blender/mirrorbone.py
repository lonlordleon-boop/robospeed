# -*- coding: utf-8 -*-
"""片側の骨の動きを、左右反転して反対側へ写す。クリップ1本ずつ。

   生成されたアニメは、片側だけ関節が折れていることがある。
   このモデルでは走りと待機が右手首を左より20〜30度余計に折っていた。
   骨の素の姿勢は左右対称（関節のずれ6〜11mm、向きのずれ0.3〜0.6度）なので、
   良いほうの側の動きをそのまま鏡写しにすれば直る。

   計算は骨の基準（素の姿勢からのずれ）の中で行う。
   世界座標で向きを x について反転する手を先に試したが、反転すると右手系が左手系になり、
   回転として成立しない。曲がりが35度から104度に増えて、かえって壊れた。

   正しくは、回転の軸だけを相手の骨の基準へ移し、角度の符号を反転する。
   鏡に映すと回る向きが逆になるので、符号の反転が要る。
   親（前腕）は写さないので、腕の振りはそのまま、手首の折れだけが直る。
   元の鍵は消してから入れ直すので、変な中間値は残らない。

   骨は「Hand」「ForeArm」のように Left/Right を外した名前で指定する。

   実行: blender -b --factory-startup -P mirrorbone.py --
         入力.glb 出力.glb クリップ名 良いほうの側 L か R [骨名,... 既定 Hand]
   例:   ... -- doll.glb out.glb Run L Hand
         クリップ名は Idle,Run,Skip のようにまとめて指定できる。6番目に AUTO で絵を元の形式のまま書き出す
   例:   ... -- girl_v55.glb out.glb Idle,Run,Skip,Walk_Adult,Walk_Child L Hand AUTO
"""
import bpy, sys, os, math
from mathutils import Matrix, Quaternion

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
CLIPS = a[2].split(',')
SIDE = a[3].upper()
NAMES = a[4].split(',') if len(a) > 4 and a[4] else ['Hand']
# 6番目に AUTO と書くと、絵を元の形式（PNG なら PNG）のまま書き出す。既定は今までどおり JPEG
IMGFMT = a[5] if len(a) > 5 and a[5] else 'JPEG'
SRCP, DSTP = ('Left', 'Right') if SIDE == 'L' else ('Right', 'Left')

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
ad = arm.animation_data
def fix_clip(CLIP):
    act = next((s.action for t in ad.nla_tracks for s in t.strips if s.action.name == CLIP), None)
    if act is None:
        print("MB クリップ %s が無い。あるのは %s"
              % (CLIP, [s.action.name for t in ad.nla_tracks for s in t.strips]))
        sys.exit(1)
    for t in ad.nla_tracks: t.mute = True
    ad.action = act
    try: ad.action_slot = act.slots[0]
    except Exception: pass
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    print("MB %s の %s を %s へ写す（%d 〜 %d フレーム）" % (CLIP, SRCP, DSTP, f0, f1))

    S3 = Matrix(((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
    MW = arm.matrix_world.to_3x3()
    MWI = MW.inverted()
    sc = bpy.context.scene

    def bend(pb):
        """その骨が親からどれだけ曲がっているか（度）。直ったか確かめるため"""
        v1 = pb.parent.tail - pb.parent.head
        v2 = pb.tail - pb.head
        return math.degrees(v1.angle(v2)) if v1.length > 1e-9 and v2.length > 1e-9 else 0.0

    plan = {}
    for nm in NAMES:
        ps, pd = arm.pose.bones.get(SRCP + nm), arm.pose.bones.get(DSTP + nm)
        if ps is None or pd is None:
            print("MB 骨 %s か %s が無い" % (SRCP + nm, DSTP + nm)); continue
        # 骨の基準の軸を、armature 空間へ出すための行列。素の姿勢なので動かない
        B_src = ps.bone.matrix_local.to_3x3()
        B_dst = pd.bone.matrix_local.to_3x3()
        M = B_dst.inverted() @ S3 @ B_src               # 軸を相手の基準へ移す（鏡を含む）
        vals, before, srcb = {}, [], []
        for f in range(f0, f1 + 1):
            sc.frame_set(f); bpy.context.view_layer.update()
            before.append(bend(pd)); srcb.append(bend(ps))
            q = ps.matrix_basis.to_3x3().to_quaternion()  # 回転の形式に関係なく読める
            q.normalize()
            vals[f] = Quaternion(M @ q.axis, -q.angle)    # 軸を移し、角度の符号を反転
        plan[nm] = (pd, vals, before)
        print("MB %s%s の曲がり 直す前 平均 %.1f度（%s%s は平均 %.1f度）"
              % (DSTP, nm, sum(before)/len(before), SRCP, nm, sum(srcb)/len(srcb)))

    def curves(action):
        return [fc for layer in action.layers for strip in layer.strips
                for cb in strip.channelbags for fc in cb.fcurves]

    for nm, (pd, vals, before) in plan.items():
        path = 'pose.bones["%s"].rotation_quaternion' % pd.name
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in [x for x in cb.fcurves if x.data_path == path]:
                        cb.fcurves.remove(fc)
        print("MB %s の元の回転の鍵を消した" % pd.name)

    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        for nm, (pd, vals, before) in plan.items():
            pd.rotation_mode = 'QUATERNION'
            pd.rotation_quaternion = vals[f]
            pd.keyframe_insert("rotation_quaternion", frame=f)

    after = {}
    for nm, (pd, vals, before) in plan.items():
        xs = []
        for f in range(f0, f1 + 1):
            sc.frame_set(f); bpy.context.view_layer.update()
            xs.append(bend(pd))
        after[nm] = xs
        print("MB %s%s の曲がり 直したあと 平均 %.1f度（直す前 %.1f度）"
              % (DSTP, nm, sum(xs)/len(xs), sum(before)/len(before)))


# クリップ名は , でつないで複数まとめて指定できる。1回の読み込みで直すので、絵の書き出しも1回で済む
for CLIP in CLIPS:
    fix_clip(CLIP)

ad.action = None
for t in ad.nla_tracks: t.mute = False
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_animation_mode='NLA_TRACKS',
                          export_skins=True, export_yup=True, export_morph=True,
                          export_image_format=IMGFMT, export_jpeg_quality=92)
print("MB 書き出し", DST, os.path.getsize(DST))
