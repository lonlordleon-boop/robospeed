# -*- coding: utf-8 -*-
"""別のモデルが持っているアニメのクリップを、こちらのモデルの骨に移す。
   骨の名前が同じで、素の姿勢もほぼ同じ（どちらも Meshy の自動リグ・Aポーズ）なので、
   Blender の「ポーズは素の姿勢からの差」という考え方のまま、そのまま貼り替えられる。
   実行: blender -b --factory-startup -P animgraft.py -- 受け側.glb 出し側.glb 出力.glb クリップ名1,クリップ名2,..."""
import bpy, sys

a = sys.argv[sys.argv.index("--")+1:]
DST_SRC, ANIM_SRC, OUT = a[0], a[1], a[2]
NAMES = a[3].split(',')

bpy.ops.wm.read_factory_settings(use_empty=True)

# --- 受け側（新しいモデル）を読む ---
bpy.ops.import_scene.gltf(filepath=DST_SRC)
before = set(bpy.data.objects)
arm_new = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
acts_before = set(bpy.data.actions)

# --- 出し側（アニメを持っているモデル）を読む ---
bpy.ops.import_scene.gltf(filepath=ANIM_SRC)
added = [o for o in bpy.data.objects if o not in before]
acts_new = [x for x in bpy.data.actions if x not in acts_before]
print("GRAFT 出し側のクリップ", [x.name for x in acts_new])

# 名前で欲しいクリップを拾う（読み込み時に .001 などが付くことがあるので前方一致で探す）
picked = []
for n in NAMES:
    hit = next((x for x in acts_new if x.name == n), None)
    if hit is None:
        hit = next((x for x in acts_new if x.name.startswith(n)), None)
    if hit is None:
        print("GRAFT 見つからない", n)
    else:
        picked.append((n, hit))

# 出し側のオブジェクトはもう要らないので、この一時的な場面からだけ外す（ファイルは触らない）
for o in added:
    bpy.data.objects.remove(o, do_unlink=True)

# --- 受け側の骨に貼る ---
if arm_new.animation_data is None:
    arm_new.animation_data_create()
ad = arm_new.animation_data
ad.action = None
# 5番目に keep と書くと、受け側がもともと持っているクリップを残したまま足す。
# 書かないと今までどおり入れ替え（受け側のクリップは消える）。
KEEP = len(a) > 4 and a[4] == 'keep'
if KEEP:
    print("GRAFT 受け側のクリップを残す", [tr.name for tr in ad.nla_tracks])
else:
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
for n, act in picked:
    act.name = n                       # 書き出し後の名前をそろえる
    tr = ad.nla_tracks.new()
    tr.name = n
    st = tr.strips.new(n, int(act.frame_range[0]), act)
    st.name = n
print("GRAFT 貼ったクリップ", [n for n, _ in picked])

# --- 書き出し ---
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_animations=True, export_animation_mode='NLA_TRACKS',
                          export_skins=True, export_yup=True, use_selection=False)
print("GRAFT 書き出し", OUT)
