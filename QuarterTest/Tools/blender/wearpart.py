# -*- coding: utf-8 -*-
"""素体に部品（髪や服）を着せる。

   着せ替え方式の道具。素体（骨とアニメ付き）に、別に生成した部品を同じ骨の下へ入れる。
   髪は「灰色の頭にカツラだけ色付き」の三面図から生成してあるので、
   テクスチャが灰色の面を頭として捨て、色の付いた面だけをカツラとして残す。
   部品の大きさと位置は、部品側の灰色の頭と素体の頭（Head の重みが強い頂点）の
   外接箱を合わせて決める。カツラは Head の骨に 100% で付ける。

   材質の名前は「hair:元気少女」のように「種類:名前」にしておく。
   dressup.html はこの名前で部品を拾って表示を切り替える。

   貼り直し（retexture）を通した部品は、灰色だった頭にも色が乗ってしまい、色では頭を
   見分けられない。その場合は貼り直す前の部品（頭が灰色のまま）を「見本」として渡す。
   見本で灰色と判定した面と、同じ位置にある面を頭として扱う（形は貼り直しで変わらない）。

   服（cloth / shoes）の場合は、灰色の素体に服だけ色付きで描いた三面図から生成する。頭も灰色で残っているので、
   合わせ方はカツラと同じく灰色の頭を球に当てはめる（灰色の点のうち上の方だけを使う）。
   骨に「body」を渡すと、1本の骨に付けるのではなく、素体の近い頂点から重みを写す（服は体と一緒に曲がる）。

   実行: blender -b --factory-startup -P wearpart.py -- 素体.glb 部品.glb 出力.glb 種類 名前 [骨 既定Head。body なら素体から重みを写す] [灰色の上限 既定0.10。「0.10,0.80」で明るさ0.80以上を白として残す] [見本.glb か ""] [倍率の掛け率 既定1.0] [ずらし x,y,z（m）既定0,0,0] [手動の大きさ 既定1.0] [ふくらませ m 既定0] [残す高さ z下,z上（m）既定すべて] [縁ならし回数 既定0] [埋まり判定の深さ m 既定0.003、0で無効] [左右別のずらし Lx,Ly,Lz;Rx,Ry,Rz]
   例:   ... -- doll.glb wig_raw.glb out.glb hair 元気少女 Head 0.10 "" 1.15 0,0,-0.06 0.9
   例:   ... -- doll.glb cloth_raw.glb out.glb cloth 元気少女 body 0.10,0.85 "" 1.0 0,0,0 1.0 0.008
   ふくらませは、服の頂点を面の向きに沿って外へ出す量。素体（下着や足先）が服を突き抜けて見えるのを防ぐ。
   残す高さは、1つの部品モデルから服と靴を分けて取り出すときに使う（服は 0.135,9、靴は -9,0.135 など）。
   種類が shoes のときは、灰色でも下を向いた低い面（靴の底）は残し、その面のテクスチャ座標を白い画素に付け替える
   （生成時に底が灰色に塗られ、灰色として消されて底が抜けていた）。
   縁ならしは、灰色との境目を面ごとに切ったギザギザを、縁の頂点を隣とならして滑らかにする回数。
   例:   ... -- doll.glb cloth_raw.glb out.glb cloth 元気少女 body 0.10,0.85 "" 1.0 0,0,0 1.07 0.008 0.135,9 3
   例:   ... -- out.glb cloth_raw.glb out2.glb shoes 元気少女 body 0.10,0.85 "" 1.0 0,0,0 1.0 0.006 -9,0.135 2
   倍率の掛け率（1.15）は自動合わせの中で掛ける値。手動の大きさとずらしは dressup.html のスライダーの値を
   そのまま渡す（cm は m に直す）。スライダーと同じく、残った部品の外接箱の中心を基準に拡大縮小してからずらす。
"""
import bpy, sys, os
import numpy as np
from mathutils import Vector, kdtree

a = sys.argv[sys.argv.index("--")+1:]
BASE, PART, OUT, KIND, NAME = a[0], a[1], a[2], a[3], a[4]
BONE = a[5] if len(a) > 5 else 'Head'
# 灰色の判定。「0.10」なら鮮やかさ 0.10 未満を灰色とみなす。「0.10,0.80」と書くと明るさ 0.80 以上は白として
# 灰色から外す（服の白い靴下・靴底・縞の白が頭と一緒に消えないように）
_g = (a[6] if len(a) > 6 else "0.10").split(',')
GREY_SAT = float(_g[0]); GREY_VMAX = float(_g[1]) if len(_g) > 1 else 1.01
MASK = a[7] if len(a) > 7 else None
EXTRA = float(a[8]) if len(a) > 8 else 1.0      # 倍率の手動の掛け率（見た目で微調整するとき）
# 手動のずらし（メートル、Blender 座標）。dressup.html のスライダーで決めた値を焼き込むときに使う
DXYZ = [float(v) for v in a[9].split(',')] if len(a) > 9 else [0.0, 0.0, 0.0]
MANUAL = float(a[10]) if len(a) > 10 else 1.0    # スライダー「大きさ」の値（残った部品の外接箱の中心を基準）
INFLATE = float(a[11]) if len(a) > 11 else 0.0   # 服を外へふくらませる量（m）。素体の突き抜け防止
ZRANGE = [float(v) for v in a[12].split(',')] if len(a) > 12 else None   # 残す高さ（world z、m）
SMOOTH = int(a[13]) if len(a) > 13 else 0        # 縁ならしの回数
# 素体に埋まった面をどれだけ深いものから消すか。0 を渡すと消さない。
# 3mm だと、股や靴の内側など、服が体に密着している所まで消してしまい穴が開いた。
BURY = float(a[14]) if len(a) > 14 else 0.003
# 左右で別々にずらす（靴を片足ずつ合わせるとき）。x の符号で分け、その側だけの外接箱の中心を基準にする。
# dressup.html の「靴の合わせ・左足／右足」と同じ計算。x>0 が左足、x<0 が右足。
SIDE = [[float(v) for v in g.split(',')] for g in a[15].split(';')] if len(a) > 15 else None

bpy.ops.wm.read_factory_settings(use_empty=True)

# ---- 素体 ----
bpy.ops.import_scene.gltf(filepath=BASE)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
# 2回目以降の着せ替えでは素体のほかに部品のメッシュもあるので、名前が body のものを優先する
body = next((o for o in bpy.data.objects if o.type == 'MESH' and o.name == 'body'), None) or next(o for o in bpy.data.objects if o.type == 'MESH')
body.name = "body"
if arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()
# 素体の頭の外接箱（Head の重みが 0.7 以上の頂点）
gi = {g.name: g.index for g in body.vertex_groups}
hidx = gi.get('Head' if BONE == 'body' else BONE)
hp = []
for v in body.data.vertices:
    w = sum(g.weight for g in v.groups if g.group == hidx)
    if w >= 0.7: hp.append(body.matrix_world @ v.co)
HP = np.array([tuple(p) for p in hp])
b_lo, b_hi = HP.min(0), HP.max(0)
print("WP 素体の頭 頂点 %d  幅 %.3f 奥行 %.3f 高さ %.3f  中心 (%.3f, %.3f, %.3f)"
      % (len(HP), *(b_hi-b_lo), *((b_lo+b_hi)/2)))

# ---- 部品 ----
before = set(o.name for o in bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=PART)
new = [o for o in bpy.data.objects if o.name not in before]
for o in list(new):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True); new.remove(o)
part = next(o for o in new if o.type == 'MESH')
part.name = KIND + "_" + NAME
# 親の変換を焼き込んで、単独のオブジェクトにする
for o in bpy.data.objects: o.select_set(False)
part.select_set(True); bpy.context.view_layer.objects.active = part
part.parent = None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 面ごとにテクスチャの色を見て、灰色（頭）か色付き（部品）かを決める
import colorsys
def grey_face_centers(obj):
    """そのオブジェクトの面のうち、テクスチャが灰色の面の中心（ローカル座標）を返す"""
    me = obj.data; uvl = me.uv_layers.active.data
    img = None
    for m in me.materials:
        if not m or not m.use_nodes: continue
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
    W, H = img.size
    A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    out = []
    for f in me.polygons:
        uv = [uvl[li].uv for li in f.loop_indices]
        cx = sum(u.x for u in uv)/len(uv); cy = sum(u.y for u in uv)/len(uv)
        c = A[min(H-1, int(cy*H)), min(W-1, int(cx*W)), :3]
        h, s, v = colorsys.rgb_to_hsv(float(c[0]), float(c[1]), float(c[2]))
        if s < GREY_SAT and v < GREY_VMAX: out.append(f.center.copy())
    return out

mesh = part.data
if MASK:
    # 見本（貼り直す前）で灰色の面を探し、同じ位置の面を頭とみなす
    before2 = set(o.name for o in bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=MASK)
    mk = [o for o in bpy.data.objects if o.name not in before2 and o.type == 'MESH' and not o.name.startswith("Icosphere")][0]
    for o in bpy.data.objects: o.select_set(False)
    mk.select_set(True); bpy.context.view_layer.objects.active = mk; mk.parent = None
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # 見本と部品は大きさが違うことがあるので、外接箱の高さで合わせてから照合する
    MP = np.array([tuple(v.co) for v in mk.data.vertices]); PP = np.array([tuple(v.co) for v in mesh.vertices])
    ks = float((PP[:,2].max()-PP[:,2].min()) / (MP[:,2].max()-MP[:,2].min()))
    off = (PP.min(0)+PP.max(0))/2 - ((MP.min(0)+MP.max(0))/2)*ks
    gc = grey_face_centers(mk)
    kd = kdtree.KDTree(len(gc))
    for i, c in enumerate(gc): kd.insert(Vector(np.array(c)*ks + off), i)
    kd.balance()
    tol = 0.004 * (PP[:,2].max()-PP[:,2].min())
    grey_faces = []; keep_faces = []
    for f in mesh.polygons:
        co, i, d = kd.find(f.center)
        (grey_faces if d < tol else keep_faces).append(f.index)
    for o in [x for x in bpy.data.objects if x.name not in before2]:
        bpy.data.objects.remove(o, do_unlink=True)
    print("WP 見本で照合: 倍率 %.3f  灰色の面 %d 個を写した" % (ks, len(gc)))
    for o in bpy.data.objects: o.select_set(False)
    part.select_set(True); bpy.context.view_layer.objects.active = part
else:
    gc_local = grey_face_centers(part)
    gset = set()
    for f in mesh.polygons:
        pass
    grey_faces = []; keep_faces = []
    gkeys = set(tuple(np.round(np.array(c)*1e5).astype(int)) for c in gc_local)
    for f in mesh.polygons:
        (grey_faces if tuple(np.round(np.array(f.center)*1e5).astype(int)) in gkeys else keep_faces).append(f.index)
print("WP 部品: 灰色（頭）の面 %d、残す面 %d" % (len(grey_faces), len(keep_faces)))

# 大きさと位置は、頭を球とみなして合わせる。
# 外接箱だと、首の切り口や、髪の裏側の灰色の面（生成時に灰色に焼かれる）で箱が膨らみ、
# 倍率が小さくなりすぎた（カツラが帽子のように頭の上に乗った）。
# 球に当てはめれば、そうした外れた点の影響が小さい。
def head_size(P, top=0.25):
    """頭の「一番広い横断面」の幅と、その断面の中心を返す。
       球の当てはめは、服の部品だと灰色が腕や脚にもあるため当てにならなかった。
       上から top の割合だけを見て（頭は全体の 4 割前後あるので頭の中に収まる）、
       高さごとの横幅を測り、一番広い断面を頭の幅とする。位置合わせもこの断面を基準にする。"""
    P = np.asarray(P, float)
    zmax = P[:,2].max(); H = zmax - P[:,2].min()
    if H <= 0: return 0.0, np.zeros(3)
    nb = 16; edges = np.linspace(zmax - top*H, zmax, nb+1)
    best = (0.0, None)
    for i in range(nb):
        m = (P[:,2] >= edges[i]) & (P[:,2] < edges[i+1])
        if m.sum() < 10: continue
        Q = P[m]; w = Q[:,0].max() - Q[:,0].min()
        if w > best[0]:
            best = (w, np.array([(Q[:,0].max()+Q[:,0].min())/2,
                                 (Q[:,1].max()+Q[:,1].min())/2,
                                 (edges[i]+edges[i+1])/2]))
    if best[1] is None: return 0.0, np.zeros(3)
    return best

def fit_sphere(P, rounds=4):
    """点群に球を最小二乗で当てはめ、外れた点を落としながら繰り返す。中心と半径を返す"""
    P = np.asarray(P, float)
    for _ in range(rounds):
        A_ = np.c_[2*P, np.ones(len(P))]; b_ = (P**2).sum(1)
        x, *_ = np.linalg.lstsq(A_, b_, rcond=None)
        c = x[:3]; r = float(np.sqrt(x[3] + (c**2).sum()))
        res = np.abs(np.linalg.norm(P - c, axis=1) - r)
        keep = res < max(0.02*r, 2.0*res.std())
        if keep.sum() < 50 or keep.all(): break
        P = P[keep]
    return c, r
cb, rb = fit_sphere(HP)
# 頭の幅で合わせるときは、素体も部品も「全身の点群の上から25%」という同じ測り方をする。
# 素体だけ頭の点群で測ると、同じ25%でも頭のてっぺんの狭い所を測ることになり、幅が小さく出た。
BP = np.array([tuple(body.matrix_world @ v.co) for v in body.data.vertices])
wb, ab = head_size(BP)
gp = set()
for fi in grey_faces:
    for vi in mesh.polygons[fi].vertices: gp.add(vi)
GP = np.array([tuple(part.matrix_world @ mesh.vertices[vi].co) for vi in gp])
cp, rp = fit_sphere(GP)
wp, ap = head_size(GP)
print("WP 素体の頭 球の半径 %.3f  一番広い断面の幅 %.3f（中心 %.3f, %.3f, %.3f）" % (rb, wb, *ab))
print("WP 部品の頭 球の半径 %.3f  一番広い断面の幅 %.3f（中心 %.3f, %.3f, %.3f）" % (rp, wp, *ap))
# 髪（カツラ）は灰色が頭だけなので球で合う。服は灰色が全身なので頭の幅で合わせる
k = float(rb / rp if KIND == 'hair' else wb / wp) * EXTRA
part.scale = (k, k, k); bpy.context.view_layer.update()
GP2 = np.array([tuple(part.matrix_world @ mesh.vertices[vi].co) for vi in gp])
if KIND == 'hair':
    cp2, _ = fit_sphere(GP2); shift = cb - cp2
else:
    _, ap2 = head_size(GP2); shift = ab - ap2
part.location = (part.location.x + shift[0], part.location.y + shift[1], part.location.z + shift[2])
bpy.context.view_layer.update()
print("WP 倍率 %.3f（手動の掛け率 %.2f 込み）  ずらし (%.3f, %.3f, %.3f)" % (k, EXTRA, *shift))
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
# 高さの範囲外の面も消す（服と靴を分けるとき）。靴の底は灰色でも残し、あとで白い画素に付け替える
sole_faces = []
if ZRANGE or KIND == 'shoes':
    gset = set(grey_faces); extra = []
    for f in mesh.polygons:
        wz = (part.matrix_world @ f.center).z
        if ZRANGE and not (ZRANGE[0] <= wz <= ZRANGE[1]):
            if f.index not in gset: extra.append(f.index)
            continue
        if KIND == "shoes" and f.index in gset and f.normal.z < -0.3 and wz < 0.035:
            gset.discard(f.index); sole_faces.append(f.index)
    grey_faces = sorted(gset) + extra
    keep_faces = [f.index for f in mesh.polygons if f.index not in set(grey_faces)]
    print("WP 高さ %s の外の面 %d 枚も消す。靴の底として残す灰色の面 %d 枚" % (ZRANGE, len(extra), len(sole_faces)))
if sole_faces:
    # 底の面のテクスチャ座標を、テクスチャの中の白い画素へ付け替える
    uvl = mesh.uv_layers.active.data
    img = None
    for m in mesh.materials:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image: img = n.image; break
    W, H = img.size
    A = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    wy, wx = np.unravel_index(np.argmax(A[:, :, :3].min(axis=2)), (H, W))   # 一番白い画素
    for fi in sole_faces:
        for li in mesh.polygons[fi].loop_indices: uvl[li].uv = ((wx + 0.5) / W, (wy + 0.5) / H)
    print("WP 底の面 %d 枚を白い画素 (%d, %d) に付け替えた" % (len(sole_faces), wx, wy))

# スライダーで決めた手動の大きさとずらし。dressup.html と同じく、残す面の頂点の外接箱の中心を基準に
# 拡大縮小してから、ずらす（頭の球の中心を基準にすると、スライダーで見た結果とずれる）。
# 高さで切り分けたあとに行うこと。靴だけを動かすときの基準は、靴の外接箱の中心でなければならない
if SIDE:
    # 左右別。x>0 を左足、x<0 を右足として、その側だけの外接箱の中心を基準に拡大縮小してずらす
    kv = set()
    for fi in keep_faces:
        for vi in mesh.polygons[fi].vertices: kv.add(vi)
    for name, sgn, d in (("左足", 1, SIDE[0]), ("右足", -1, SIDE[1] if len(SIDE) > 1 else SIDE[0])):
        idx = [vi for vi in kv if (mesh.vertices[vi].co.x > 0) == (sgn > 0)]
        if not idx: continue
        KP = np.array([tuple(mesh.vertices[vi].co) for vi in idx])
        c0 = (KP.min(0) + KP.max(0)) / 2
        allidx = [v.index for v in mesh.vertices if (v.co.x > 0) == (sgn > 0)]
        for vi in allidx:
            p = np.array(mesh.vertices[vi].co)
            mesh.vertices[vi].co = tuple(c0 + MANUAL * (p - c0) + np.array(d))
        print("WP 手動 %s: 大きさ %.2f（中心 %.3f, %.3f, %.3f）  ずらし (%.3f, %.3f, %.3f)" % (name, MANUAL, *c0, *d))
elif MANUAL != 1.0 or any(DXYZ):
    kv = set()
    for fi in keep_faces:
        for vi in mesh.polygons[fi].vertices: kv.add(vi)
    KP = np.array([tuple(mesh.vertices[vi].co) for vi in kv])
    c0 = (KP.min(0) + KP.max(0)) / 2
    for v in mesh.vertices:
        p = np.array(v.co); v.co = tuple(c0 + MANUAL * (p - c0) + np.array(DXYZ))
    print("WP 手動: 大きさ %.2f（中心 %.3f, %.3f, %.3f）  ずらし (%.3f, %.3f, %.3f)" % (MANUAL, *c0, *DXYZ))

# 灰色の面を消す
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
for fi in grey_faces: mesh.polygons[fi].select = True
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='FACE'); bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.delete_loose()
# 灰色を切ったあとに残る小さな穴（数辺の輪）を塞ぐ。襟・袖口・裾・靴の口のような本物の開口は
# 数十辺あるので、辺の数が少ない輪だけを埋める
bpy.ops.object.mode_set(mode='OBJECT')
print("WP 消したあとの面 %d、頂点 %d" % (len(mesh.polygons), len(mesh.vertices)))
if INFLATE:
    # 頂点をその法線の向きに少し押し出す。服と素体の間にすき間を作り、動いたときの突き抜けを減らす。
    # glTF から読んだメッシュは UV の継ぎ目で頂点が分かれていて、そのまま押し出すと継ぎ目が裂けて
    # 白い斑点だらけになった。先に同じ位置の頂点をつないでから押し出す（UV は面側に残るので崩れない）
    import bmesh
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(mesh); bm.free(); mesh.update()
    for v in mesh.vertices: v.co = v.co + v.normal * INFLATE
    print("WP ふくらませ %.3f m（同じ位置の頂点をつないだあと 頂点 %d）" % (INFLATE, len(mesh.vertices)))
    # 素体の中に埋まっている面を消す。灰色の判定をすり抜けた素体の面が、裾から細長い破片として残り、
    # dressup.html で服の下の素体を隠したときにトゲのように見えた。
    # 頂点ごとに一番近い素体の頂点を探し、その面の向きで内側（3mm より深い）にある頂点だけの面を消す
    buried = []
    if BURY > 0:
        bpos = [body.matrix_world @ v.co for v in body.data.vertices]
        bnrm = [(body.matrix_world.to_3x3() @ v.normal).normalized() for v in body.data.vertices]
        kdb = kdtree.KDTree(len(bpos))
        for i, p in enumerate(bpos): kdb.insert(p, i)
        kdb.balance()
        inside = []
        for v in mesh.vertices:
            co, i, d = kdb.find(v.co)
            inside.append((v.co - co).dot(bnrm[i]) < -BURY)
        buried = [f.index for f in mesh.polygons if all(inside[vi] for vi in f.vertices)]
    if buried:
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT'); bpy.ops.object.mode_set(mode='OBJECT')
        for fi in buried: mesh.polygons[fi].select = True
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.delete(type='FACE')
        bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.delete_loose(); bpy.ops.object.mode_set(mode='OBJECT')
    print("WP 素体に埋まっていた面 %d 枚を消した（深さ %.3f m）→ 面 %d、頂点 %d" % (len(buried), BURY, len(mesh.polygons), len(mesh.vertices)))

if SMOOTH:
    # 縁ならし。灰色との境目は面ごとに切れてギザギザなので、縁（片側にしか面がない辺）の頂点を
    # 縁の隣の頂点との中点へ寄せる。内側の頂点は動かさない
    import bmesh
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
    for _ in range(SMOOTH):
        nb = {}
        for e in bm.edges:
            if e.is_boundary:
                v0, v1 = e.verts
                nb.setdefault(v0, []).append(v1.co.copy()); nb.setdefault(v1, []).append(v0.co.copy())
        for v, cos in nb.items():
            if len(cos) >= 2: v.co = v.co * 0.4 + (sum(cos, Vector()) / len(cos)) * 0.6
    bm.to_mesh(mesh); bm.free(); mesh.update()
    print("WP 縁ならし %d 回（縁の頂点 %d 個）" % (SMOOTH, len(nb)))
# 仕上げに、灰色を切ったあとに残った小さな穴を塞ぐ。
# 襟・袖口・裾・靴の口のような本物の開口は数十辺あるので、辺の少ない輪だけを埋める。
# 同じ位置の頂点をつないでからでないと、穴が穴として見つからない（UV の継ぎ目で分かれているため）
import bmesh as _bm
_b = _bm.new(); _b.from_mesh(mesh)
_bm.ops.remove_doubles(_b, verts=_b.verts, dist=1e-5)
_be = [e for e in _b.edges if e.is_boundary]
_r = _bm.ops.holes_fill(_b, edges=_be, sides=12)
print("WP 小さな穴を %d 枚の面で塞いだ（縁の辺 %d 本）" % (len(_r.get('faces', [])), len(_be)))
_b.to_mesh(mesh); _b.free(); mesh.update()

# 材質の名前を「種類:名前」にする（dressup.html がこれで拾う）
for m in mesh.materials:
    if m: m.name = "%s:%s" % (KIND, NAME)

# 骨に付ける
if BONE == 'body':
    # 素体の近い頂点（4点）の重みを距離で加重平均して写す。服は体と同じ骨で曲がる
    bpos = [body.matrix_world @ v.co for v in body.data.vertices]
    kd = kdtree.KDTree(len(bpos))
    for i, p in enumerate(bpos): kd.insert(p, i)
    kd.balance()
    names = [g.name for g in body.vertex_groups]
    vgs = {n: part.vertex_groups.new(name=n) for n in names}
    for v in mesh.vertices:
        hits = kd.find_n(v.co, 4)
        acc = {}; tot = 0.0
        for co, i, d in hits:
            w = 1.0 / (d + 1e-4); tot += w
            for g in body.data.vertices[i].groups:
                acc[g.group] = acc.get(g.group, 0.0) + w * g.weight
        for gi_, val in acc.items():
            if val / tot > 1e-3: vgs[names[gi_]].add([v.index], val / tot, 'REPLACE')
    print("WP 重みを素体から写した: 頂点 %d、骨 %d" % (len(mesh.vertices), len(names)))
else:
    vg = part.vertex_groups.new(name=BONE)
    vg.add([v.index for v in mesh.vertices], 1.0, 'REPLACE')
for o in bpy.data.objects: o.select_set(False)
part.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_NAME')

bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True)
print("WP 書き出し", OUT, os.path.getsize(OUT))
