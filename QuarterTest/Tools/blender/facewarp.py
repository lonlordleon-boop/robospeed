# -*- coding: utf-8 -*-
# 顔の歪みを測る。顔の前面の頂点を、コマごとに「頭の骨から見た位置」に直し、素の姿勢からどれだけずれたかを出す。
# 顔が頭と一緒に丸ごと動いていれば 0。腰や腕の重みが混ざっていると、動きに引っ張られてずれる。
# 実行: blender -b --factory-startup -P facewarp.py -- "a.glb;b.glb" Skip,Run [コマ数 24]
# 目安: 元気少女 v55 はスキップで最大 0.10cm。秀才少女は直す前 2.94cm（スキップで顔がぐにゃぐにゃ）→ headclean.py で 0。
import bpy, sys
import numpy as np
from mathutils import Matrix
a = sys.argv[sys.argv.index("--")+1:]
CLIPS = a[1].split(','); N = int(a[2]) if len(a) > 2 else 24
for SRC in a[0].split(';'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    me = next(o for o in bpy.data.objects if o.type == 'MESH')
    if arm.animation_data is None: arm.animation_data_create()
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    arm.animation_data.action = None
    for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    def verts():
        em = me.evaluated_get(dg).to_mesh()
        return np.array([tuple(me.matrix_world @ v.co) for v in em.vertices])
    R = verts()
    SC = arm.matrix_world.to_scale()[0]   # 骨の座標は外枠の大きさ（1/100 など）で縮んでいるので、m に戻す倍率
    hb = arm.pose.bones['Head']
    H0 = np.array(arm.matrix_world @ hb.matrix)
    # 顔の前面: 鼻の高さ付近を中心に、あご〜おでこ、正面向き
    face = (np.abs(R[:, 0]) < 0.15) & (R[:, 2] > 0.68) & (R[:, 2] < 0.95) & (R[:, 1] < -0.18)
    Rl = (np.linalg.inv(H0) @ np.c_[R[face], np.ones(face.sum())].T).T[:, :3]
    out = []
    for CLIP in CLIPS:
        act = bpy.data.actions.get(CLIP); arm.animation_data.action = act
        f0, f1 = act.frame_range; worst = [];
        for k in range(N):
            bpy.context.scene.frame_set(int(round(f0 + (f1 - f0) * k / N))); bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            V = verts()[face]
            Hk = np.array(arm.matrix_world @ arm.pose.bones['Head'].matrix)
            Vl = (np.linalg.inv(Hk) @ np.c_[V, np.ones(len(V))].T).T[:, :3]
            d = (Vl - Rl) * SC; d -= d.mean(0)   # 顔全体の平行移動は除く（形の崩れだけを見る）。SC で骨の座標から m に直す
            worst.append(np.linalg.norm(d, axis=1))
        W = np.array(worst)
        out.append("%s 平均%.2fcm 最大%.2fcm" % (CLIP, 100 * W.mean(), 100 * W.max()))
    print("FW %s 顔の点%d  %s" % (SRC.split('/')[-1], face.sum(), "  ".join(out)))
