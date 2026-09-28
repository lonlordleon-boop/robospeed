# -*- coding: utf-8 -*-
"""犬に骨を入れる（Rigify の basic_quadruped メタリグを体に合わせて使う）。

   ・メタリグの骨を、犬の体の寸法に合わせて置き直す
   ・rigify_generate で本生成し、メッシュを自動ウェイトで結ぶ
   ・試しのポーズを付けて、正面・横・斜めの絵を出す
   ・骨入りの glb を書き出す

   【注意】Rigify を使うので --factory-startup を付けないこと。
           付けると本生成が 'make_custom_pivot' で落ちる。

   実行: blender -b -P dog_rig.py -- 入力.glb 出力フォルダ [骨の座標.json]
   出力: dog_rigged.glb と、確かめ用の絵 check_rig.png

   3つめの引数を渡すと、骨の座標をその JSON から読む（dogfit.py が出したもの）。
   渡さない時は、下の BONES（仮モデルの寸法を手で測った値）を使う。
"""
import bpy, addon_utils, sys, os, math, json, traceback
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
SRC = os.path.abspath(a[0])
OUT = os.path.abspath(a[1])
FIT = os.path.abspath(a[2]) if len(a) > 2 else None
os.makedirs(OUT, exist_ok=True)

LOG = []
def log(s):
    LOG.append(str(s)); print("[rig] " + str(s))

# ---------------------------------------------------------------- 犬の寸法
# dog_build.py が置いた場所に合わせてある（Blender 座標・Z が上・前は -Y）。
# 別のメッシュに入れ替える時は、ここだけ測り直す。
FRONT_X, REAR_X = 0.072, 0.082          # 前脚・後脚の左右の位置
BONES = {
    # --- 胴（後ろ→前）。spine.004 が根もとで、そこから尻尾と胴に分かれる
    'spine.004':  ((0,  0.240, 0.500), (0,  0.200, 0.450)),
    'spine.005':  ((0,  0.200, 0.450), (0,  0.080, 0.432)),
    'spine.006':  ((0,  0.080, 0.432), (0, -0.040, 0.425)),
    'spine.007':  ((0, -0.040, 0.425), (0, -0.140, 0.432)),
    'spine.008':  ((0, -0.140, 0.432), (0, -0.215, 0.470)),   # 胸（肩がここに付く）
    'spine.009':  ((0, -0.215, 0.470), (0, -0.255, 0.528)),   # 首
    'spine.010':  ((0, -0.255, 0.528), (0, -0.300, 0.585)),   # 首
    'spine.011':  ((0, -0.300, 0.585), (0, -0.470, 0.592)),   # 頭〜鼻づら
    # --- 尻尾（背中へ巻く。dog_build.py の弧に合わせてある）
    'spine.003':  ((0,  0.240, 0.500), (0,  0.185, 0.600)),
    'spine.002':  ((0,  0.185, 0.600), (0,  0.220, 0.686)),
    'spine.001':  ((0,  0.220, 0.686), (0,  0.320, 0.688)),
    'spine':      ((0,  0.320, 0.688), (0,  0.370, 0.600)),
    # --- 前脚（左。右は x を反転して作る）
    'shoulder.L':     (( 0.035, -0.130, 0.460), (FRONT_X, -0.165, 0.375)),
    'front_thigh.L':  ((FRONT_X, -0.165, 0.360), (FRONT_X, -0.155, 0.250)),
    'front_shin.L':   ((FRONT_X, -0.155, 0.250), (FRONT_X, -0.185, 0.120)),
    'front_foot.L':   ((FRONT_X, -0.185, 0.120), (FRONT_X, -0.175, 0.030)),
    'front_toe.L':    ((FRONT_X, -0.175, 0.030), (FRONT_X, -0.235, 0.012)),
    # --- 後脚（左）。ひざは前、飛節は後ろへ曲げる（まっすぐだと IK が効かない）
    'thigh.L':    ((REAR_X,  0.160, 0.390), (REAR_X,  0.155, 0.260)),
    'shin.L':     ((REAR_X,  0.155, 0.260), (REAR_X,  0.200, 0.130)),
    'foot.L':     ((REAR_X,  0.200, 0.130), (REAR_X,  0.185, 0.030)),
    'toe.L':      ((REAR_X,  0.185, 0.030), (REAR_X,  0.135, 0.012)),
    # --- 骨盤と胸の飾り骨
    'pelvis.L':   ((0,  0.220, 0.450), ( 0.060, 0.160, 0.560)),
    'breast.L':   (( 0.030, -0.120, 0.400), ( 0.030, -0.220, 0.330)),
}

# dogfit.py が測った座標があれば、そちらで上書きする
if FIT:
    with open(FIT, encoding='utf-8') as f:
        _fit = json.load(f)
    BONES = {k: (tuple(v[0]), tuple(v[1])) for k, v in _fit['bones'].items()}
    FRONT_X = abs(BONES['front_thigh.L'][0][0])
    REAR_X = abs(BONES['thigh.L'][0][0])

def mirror(v):
    return (-v[0], v[1], v[2])

# ---------------------------------------------------------------- 読み込み
# 場面を空にする。read_factory_settings は使わない（アドオンの設定まで戻され、Rigify が無効になる）
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
addon_utils.enable("rigify", default_set=True, persistent=True)
bpy.ops.import_scene.gltf(filepath=SRC)
mesh = next((o for o in bpy.context.scene.objects if o.type == 'MESH'), None)
if mesh is None:
    log("メッシュが見つからない"); sys.exit(1)
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
V = np.array([tuple(mesh.matrix_world @ v.co) for v in mesh.data.vertices])
log("メッシュ: 頂点 %d / 高さ %.3f / 前後 %.3f〜%.3f / 幅 %.3f"
    % (len(V), V[:, 2].max(), V[:, 1].min(), V[:, 1].max(), V[:, 0].max() - V[:, 0].min()))

# ---------------------------------------------------------------- メタリグを体に合わせる
bpy.ops.object.armature_basic_quadruped_metarig_add()
meta = bpy.context.active_object
meta.name = 'dog_metarig'
bpy.ops.object.mode_set(mode='EDIT')
eb = meta.data.edit_bones
rolls = {b.name: b.roll for b in eb}          # 元の roll は残す（rig の向きの決まりが入っている）
moved = 0
for name, (h, t) in BONES.items():
    for nm, hh, tt in ((name, h, t),) if not name.endswith('.L') else (
            (name, h, t), (name[:-2] + '.R', mirror(h), mirror(t))):
        b = eb.get(nm)
        if b is None:
            log("  骨が無い: " + nm); continue
        b.head = Vector(hh); b.tail = Vector(tt); b.roll = rolls.get(nm, 0.0)
        moved += 1
log("置き直した骨: %d 本 / メタリグ全体 %d 本" % (moved, len(eb)))
bpy.ops.object.mode_set(mode='OBJECT')

# 脚の節を1本ずつにする（既定は2本。短い脚だと細かすぎて、すねに重みが付かない）
seg = []
for nm in ('front_thigh.L', 'front_thigh.R', 'thigh.L', 'thigh.R'):
    pb = meta.pose.bones.get(nm)
    if pb is None: continue
    try:
        pb.rigify_parameters.segments = 1
        seg.append(nm)
    except Exception as e:
        log("  節の数を変えられない %s: %r" % (nm, e))
log("脚の節を1本にした: " + (", ".join(seg) if seg else "（できず）"))

# ---------------------------------------------------------------- 本生成
try:
    bpy.context.view_layer.objects.active = meta
    bpy.ops.pose.rigify_generate()
    rig = bpy.context.active_object
    defs = [b.name for b in rig.data.bones if b.name.startswith('DEF-')]
    log("本生成: できた（%s / 骨 %d 本 / うち変形用 DEF- が %d 本）" % (rig.name, len(rig.data.bones), len(defs)))
except Exception:
    log("本生成: 失敗\n" + traceback.format_exc()); sys.exit(1)

# ---------------------------------------------------------------- メッシュを骨へ結ぶ
def weighted_bones(ob):
    n = 0
    for g in ob.vertex_groups:
        i = g.index
        if any(any(x.group == i and x.weight > 0.001 for x in v.groups) for v in ob.data.vertices):
            n += 1
    return n

# 自動ウェイト（熱の計算）は、面がつながっていないと1本も解けない。
# 生成モデルの glb は UV の切れ目で頂点が分かれているので、そのままだと必ず失敗する。
# 溶接したコピーで計算し、重みを元のメッシュへ位置で写す（元の UV は壊さない）
def auto_weights_via_weld():
    from mathutils import kdtree
    tmp = mesh.copy(); tmp.data = mesh.data.copy(); tmp.name = 'weld_tmp'
    bpy.context.collection.objects.link(tmp)
    bpy.ops.object.select_all(action='DESELECT')
    tmp.select_set(True); bpy.context.view_layer.objects.active = tmp
    for g in list(tmp.vertex_groups): tmp.vertex_groups.remove(g)
    before = len(tmp.data.vertices)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=1e-4)
    bpy.ops.object.mode_set(mode='OBJECT')
    log("  溶接: 頂点 %d → %d" % (before, len(tmp.data.vertices)))
    bpy.ops.object.select_all(action='DESELECT')
    tmp.select_set(True); rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    ok = False
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        ok = weighted_bones(tmp) > 0
    except Exception:
        ok = False
    log("  溶接したコピーの自動ウェイト: %s（重みの付いた骨 %d 本）" % ("できた" if ok else "だめ", weighted_bones(tmp)))
    if not ok:
        bpy.data.objects.remove(tmp, do_unlink=True); return False
    # 位置で写す。溶接は同じ場所の頂点をまとめただけなので、一番近い頂点が元の相手
    kd = kdtree.KDTree(len(tmp.data.vertices))
    for i, v in enumerate(tmp.data.vertices): kd.insert(v.co, i)
    kd.balance()
    for g in tmp.vertex_groups:
        if g.name not in mesh.vertex_groups: mesh.vertex_groups.new(name=g.name)
    tnames = {g.index: g.name for g in tmp.vertex_groups}
    for v in mesh.data.vertices:
        _, i, _ = kd.find(v.co)
        for gg in tmp.data.vertices[i].groups:
            if gg.weight > 0.0005:
                mesh.vertex_groups[tnames[gg.group]].add([v.index], gg.weight, 'REPLACE')
    bpy.data.objects.remove(tmp, do_unlink=True)
    # メッシュ本体にも Armature をつなぐ
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_NAME')
    return True

how = "自動ウェイト（溶接したコピーから写した）"
if not auto_weights_via_weld():
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    how = "自動ウェイト"
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        if weighted_bones(mesh) == 0: raise RuntimeError('重みが1つも付かなかった')
    except Exception:
        how = "エンベロープ（自動ウェイトが失敗したため）"
        bpy.ops.object.select_all(action='DESELECT')
        mesh.select_set(True); rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.parent_set(type='ARMATURE_ENVELOPE')
cnt = {g.index: 0 for g in mesh.vertex_groups}
for v in mesh.data.vertices:
    for gg in v.groups:
        if gg.weight > 0.001: cnt[gg.group] = cnt.get(gg.group, 0) + 1
named = sorted(((g.name, cnt.get(g.index, 0)) for g in mesh.vertex_groups), key=lambda x: -x[1])
zero = [n for n, c in named if c == 0]
log("結び方: %s / 骨 %d 本 / 重みの付いた頂点がある骨 %d 本" % (how, len(named), len(named) - len(zero)))
log("  多い順: " + ", ".join("%s=%d" % nc for nc in named[:8]))
if zero: log("  頂点が1つも付かない骨（%d 本）: %s" % (len(zero), ", ".join(zero)))

# 自動ウェイトが届かなかった骨を、骨からの距離で埋める。
# 脚の節のように短くて隣の骨に挟まれた所は、熱の計算だと0になることがある
def fill_by_distance(names):
    if not names: return
    dbones = rig.data.bones
    for nm in names:
        b = dbones.get(nm)
        if b is None: continue
        h, t = Vector(b.head_local), Vector(b.tail_local)
        ab = t - h; L2 = ab.length_squared
        if L2 <= 0: continue
        rad = ab.length * 0.75                      # この太さまでを、その骨の持ち分にする
        g = mesh.vertex_groups[nm]
        n = 0
        for v in mesh.data.vertices:
            p = Vector(v.co)
            u = max(0.0, min(1.0, (p - h).dot(ab) / L2))
            d = (p - (h + ab * u)).length
            if d < rad:
                w = 1.0 - (d / rad)                 # 近いほど強く
                g.add([v.index], w * w, 'REPLACE')
                n += 1
        log("  距離で埋めた: %s → 頂点 %d 個" % (nm, n))
    # 重みの合計を1にそろえる
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    bpy.context.view_layer.objects.active = rig

fill_by_distance(zero)

# どの骨にも結ばれなかった頂点を、一番近い「結ばれている頂点」の真似をさせる。
# （耳の先や尻尾の先のように、熱の計算が届かない出っぱりが残る。放っておくとそこだけ動かず取り残される）
# 頂点ごとに別々の骨へ付けると、尻尾の先のように体に重なった所で一部だけがお尻に付き、
# そこだけ引っぱられて細く伸びる。つながった「かたまり」ごと1本の骨に付けると、これが起きない
def fill_orphan_verts():
    from mathutils import kdtree
    vs = mesh.data.vertices
    w = [sum(g.weight for g in v.groups) > 1e-5 for v in vs]
    if all(w):
        log("  どの骨にも付いていない頂点: 0 個"); return
    # 辺でつながった「かたまり」に分ける（この仮モデルは風船を並べた作りなので、
    # 耳や尻尾の先が、まわりとつながっていない別のかたまりになっている）
    adj = [[] for _ in vs]
    for e in mesh.data.edges:
        x, y = e.vertices
        adj[x].append(y); adj[y].append(x)
    comp = [-1] * len(vs); groups = []
    for i in range(len(vs)):
        if comp[i] >= 0: continue
        g = [i]; comp[i] = len(groups); k = 0
        while k < len(g):
            a0 = g[k]; k += 1
            for b0 in adj[a0]:
                if comp[b0] < 0: comp[b0] = len(groups); g.append(b0)
        groups.append(g)
    have = [i for i in range(len(vs)) if w[i]]
    kd = kdtree.KDTree(len(have))
    for k, i in enumerate(have): kd.insert(vs[i].co, k)
    kd.balance()
    from collections import Counter
    n_v = n_g = 0
    for g in groups:
        if any(w[i] for i in g): continue          # 重みが付いている所は触らない
        vote = Counter()                           # かたまりごとに、行き先の骨を1本に決める
        for i in g:
            _, k, _ = kd.find(vs[i].co)
            src = vs[have[k]]
            best = max(src.groups, key=lambda x: x.weight)
            vote[mesh.vertex_groups[best.group].name] += 1
        nm = vote.most_common(1)[0][0]
        # かたまりごと1本の骨に付ける。頂点ごとに別の骨へ付けると、そこだけ伸びてちぎれる
        mesh.vertex_groups[nm].add(g, 1.0, 'REPLACE')
        n_v += len(g); n_g += 1
        log("    かたまり（頂点 %d 個）→ %s" % (len(g), nm))
    log("  どの骨にも付いていなかった頂点: %d 個 / %d かたまり → まとめて骨に付けた" % (n_v, n_g))

fill_orphan_verts()

# ---------------------------------------------------------------- 試しのポーズ
def rot(bone, axis, deg):
    pb = rig.pose.bones.get(bone)
    if pb is None: return None
    pb.rotation_mode = 'XYZ'
    v = list(pb.rotation_euler); v['XYZ'.index(axis)] = math.radians(deg)
    pb.rotation_euler = v
    return bone
def move(bone, d):
    pb = rig.pose.bones.get(bone)
    if pb is None: return None
    pb.location = Vector(pb.location) + Vector(d)
    return bone

bpy.ops.object.mode_set(mode='POSE')
posed = []
# 走っている途中のような形：左前脚を前へ振り上げ、右後脚を後ろへ蹴る。首と尻尾も動かす
for f in (move('front_foot_ik.L', (0, -0.10, 0.09)),   # 左前脚を前・上へ
          move('foot_ik.R',       (0, 0.09, 0.07)),    # 右後脚を後ろ・上へ
          rot('neck', 'X', -14), rot('head', 'X', -10),
          rot('spine.001', 'X', -18), rot('spine.002', 'X', -18)):   # 尻尾
    if f: posed.append(f)
log("試しに動かした骨: " + (", ".join(posed) if posed else "（名前が合わず、1本も動かせなかった）"))
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
ev = mesh.evaluated_get(dg)
P2 = np.array([tuple(mesh.matrix_world @ v.co) for v in ev.to_mesh().vertices])
d = np.linalg.norm(P2 - V, axis=1)
log("ポーズによる動き: 一番動いた頂点 %.3f / 平均 %.4f / 1mm以上動いた頂点 %d 個（%.0f%%）"
    % (d.max(), d.mean(), int((d > 0.001).sum()), 100.0 * (d > 0.001).mean()))
ev.to_mesh_clear()

# ---------------------------------------------------------------- 確かめの絵
sc = bpy.context.scene
cam_d = bpy.data.cameras.new('cam'); cam_d.type = 'ORTHO'
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_shadows = True
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('w'); sc.world = w; w.color = (1, 1, 1)
sc.render.resolution_x = 360; sc.render.resolution_y = 300
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, 0))
rig.hide_render = True                                   # 骨は写さない（形の崩れだけを見る）
files = []
for az in (0, 90, 35):
    cam_d.ortho_scale = 1.3
    d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(12)),
                -math.cos(math.radians(az)) * math.cos(math.radians(12)), math.sin(math.radians(12))))
    cam.location = Vector((0, -0.05, 0.38)) + d * 6
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    fn = os.path.join(OUT, 'rig_%d.png' % az); files.append(fn)
    sc.render.filepath = fn; bpy.ops.render.render(write_still=True)
imgs = [bpy.data.images.load(f) for f in files]
w_, h_ = imgs[0].size
buf = np.ones((h_, w_ * len(imgs), 4), dtype=np.float32)
for k, im in enumerate(imgs):
    px = np.empty(w_ * h_ * 4, dtype=np.float32); im.pixels.foreach_get(px)
    buf[:, k * w_:(k + 1) * w_] = px.reshape(h_, w_, 4)
o_ = bpy.data.images.new('j', w_ * len(imgs), h_); o_.pixels.foreach_set(buf.ravel())
o_.filepath_raw = os.path.join(OUT, 'check_rig.png'); o_.file_format = 'PNG'; o_.save()
log("絵: " + os.path.join(OUT, 'check_rig.png'))

# ---------------------------------------------------------------- 書き出し
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True); rig.select_set(True)
bpy.context.view_layer.objects.active = rig
path = os.path.join(OUT, 'dog_rigged.glb')
bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                          export_animations=False, export_skins=True, export_yup=True)
log("書き出し: %s (%d バイト)" % (path, os.path.getsize(path)))

with open(os.path.join(OUT, 'rig_log.txt'), 'w', encoding='utf-8') as f:
    f.write("\n".join(LOG))
# 動きを付ける道具（dog_run.py）が使えるよう、リグを保ったまま .blend でも保存する。
# 試しのポーズは消しておく（素の状態から動きを作れるように）
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.transforms_clear()
bpy.ops.object.mode_set(mode='OBJECT')
blend = os.path.join(OUT, 'dog_rig.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend)
log("保存: %s（ウインドウは開かない。dog_run.py がこれを読む）" % blend)

print("[rig] DONE")
