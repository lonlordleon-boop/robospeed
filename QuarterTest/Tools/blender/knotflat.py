# -*- coding: utf-8 -*-
"""服の表面から小さくくしゃっと飛び出した面のかたまり（結び目）を、まわりの表面になじませて平らにする。面は消さない。
   骨・重み・動き・絵はそのまま、頂点の位置だけ。
   お嬢様（小学生編）は、右肩のうしろ（高さ 0.81m）の、髪と服を切り離した所に、小さな服の面が星形にくしゃっと固まって
   表面から飛び出していた。髪の房のすき間に刺さって、横から見ると髪の中に白いかけらが散って見えた（「右肩の白いかけら」）。
   髪に隠れた服を髪の色で塗る方法は、横から見て肩に黒い筋が出るので不採用（前に言われた「肩に髪が付いてる」になる）
   1) 箱の中の明るい面（服）のうち、小さい面（一番長い辺 < EMAX）で、まわり（RN 以内）の大きい服の面の向きの平均と
      向きが大きく違う（内積 < DOT）もの＝結び目の面。結び目の面とつながる小さい面も、向きが違えば足していく
   2) 結び目の面の頂点を動かす頂点、それ以外を止める頂点にして、動かす頂点をとなりの頂点の平均へ NIT 回寄せる
      （まわりの表面に張った膜のようになる）。同じ位置の頂点（絵の切れ目）は一緒に動かす（片方だけ動かすと穴になる）
   実行: blender -b --factory-startup -P knotflat.py -- 入力.glb 出力.glb x0,x1,y0,y1,z0,z1 [--emax 0.02] [--dot 0.5] [--list]
   --list は動かさずに結び目の面の番号だけ出す（確かめ用）
   --collapse f1,f2,.. は指定の面を位置も重みも 1 点に潰す（お嬢様の右肩：4817,3643,3648。箱は 0,0,0,0,0,0 でよい）"""
import bpy, bmesh, sys, colorsys, numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
EMAX = float(opt('--emax', 0.02)); DOT = float(opt('--dot', 0.5)); RN = 0.025; NIT = 200
LIST = '--list' in a
if LIST: a.remove('--list')
# --collapse f1,f2,..：指定の面を 1 点に潰す（頂点を面の真ん中へ集め、重みも平均にそろえる）。結び目をならしたあとも、
#   右肩の 4817 番の面は頂点ごとに腕と肩の重みが違い、待機の姿勢で横に細長く引き伸ばされて、白い棚のように見えた。
#   重みをそろえないと、位置を集めても動くとまた離れる。箱は使わない（箱を与えても無視する）
CFACES = [int(x) for x in opt('--collapse', '').split(',') if x]
SRC, OUT = a[0], a[1]; BOX = tuple(map(float, a[2].split(',')))
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
MW = me.matrix_world; MI = MW.inverted(); N3 = MW.to_3x3()
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
bm = bmesh.new(); bm.from_mesh(m); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table(); uvL = bm.loops.layers.uv.active
if CFACES:
    dfl = bm.verts.layers.deform.active
    for fi in CFACES:
        posg = {}   # 潰すたびに作り直す（前の面で動いた頂点がある）
        for v in bm.verts: posg.setdefault(tuple(round(x, 6) for x in v.co), []).append(v)
        f = bm.faces[fi]; ks = {tuple(round(x, 6) for x in v.co) for v in f.verts}
        vs = [u for k in ks for u in posg[k]]
        c = sum((v.co for v in f.verts), Vector()) / len(f.verts)
        w = {}
        for v in vs:
            for g, x in v[dfl].items(): w[g] = w.get(g, 0.0) + x / len(vs)
        s = sum(w.values()); w = {g: x / s for g, x in w.items()}
        mv = max((MW @ v.co - MW @ c).length for v in vs)
        for v in vs:
            v.co = c; d = v[dfl]
            for g in list(d.keys()): del d[g]
            for g, x in w.items(): d[g] = x
        print("KF 面 %d を 1 点に潰した（頂点 %d・一番動いた長さ %.4f）" % (fi, len(vs), mv))
    bm.to_mesh(m); m.update(); bm.free()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
    print("KF 書き出し", OUT); sys.exit(0)
def light(f):
    uv = np.mean([l[uvL].uv[:] for l in f.loops], 0)
    return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])[2] >= 0.6
def inb(c): return BOX[0] <= c.x <= BOX[1] and BOX[2] <= c.y <= BOX[3] and BOX[4] <= c.z <= BOX[5]
FC = {f.index: MW @ f.calc_center_median() for f in bm.faces}
FN = {f.index: (N3 @ f.normal).normalized() for f in bm.faces}
def emax(f):
    p = [MW @ v.co for v in f.verts]; return max((p[i] - p[(i + 1) % len(p)]).length for i in range(len(p)))
LT = {f.index: light(f) for f in bm.faces if inb(FC[f.index])}
# まわりの大きい服の面（向きの手本）
big = [f for f in bm.faces if f.index in LT and LT[f.index] and emax(f) >= EMAX]
kd = KDTree(len(big))
for i, f in enumerate(big): kd.insert(FC[f.index], i)
kd.balance()
def refn(c):
    s = Vector()
    for _, i, _ in kd.find_range(c, RN): f = big[i]; s += FN[f.index] * f.calc_area()
    return s.normalized() if s.length > 0 else None
def odd(f):
    if f.index not in LT or not LT[f.index] or emax(f) >= EMAX: return False
    r = refn(FC[f.index]); return r is not None and FN[f.index].dot(r) < DOT
K = {f.index for f in bm.faces if odd(f)}
# 結び目の面とつながる小さい面で向きが違うものを足す
grow = True
while grow:
    grow = False
    for fi in list(K):
        for v in bm.faces[fi].verts:
            for g in v.link_faces:
                if g.index not in K and odd(g): K.add(g.index); grow = True
print("KF 結び目の面 %d" % len(K)); print("KF 面", ",".join(map(str, sorted(K))))
if not LIST:
    posg = {}
    for v in bm.verts: posg.setdefault(tuple(round(x, 6) for x in v.co), []).append(v)
    def key(v): return tuple(round(x, 6) for x in v.co)
    mv = {key(v) for fi in K for v in bm.faces[fi].verts}
    # 結び目の外の頂点とつながる所は止める（ふちの頂点は、結び目の面にしか付いていなければ動かす）
    fix = set()
    for k in mv:
        for v in posg[k]:
            if any(g.index not in K for g in v.link_faces): fix.add(k)
    free = mv - fix
    nb = {k: set() for k in free}
    for k in free:
        for v in posg[k]:
            for e in v.link_edges: nb[k].add(key(e.other_vert(v)))
        nb[k].discard(k)
    P = {k: posg[k][0].co.copy() for k in set().union(*nb.values()) | free}
    P0 = {k: P[k].copy() for k in free}
    for _ in range(NIT):
        for k in free:
            if nb[k]: P[k] = sum((P[j] for j in nb[k]), Vector()) / len(nb[k])
    mx = 0.0
    for k in free:
        for v in posg[k]: v.co = P[k]
        mx = max(mx, (MW @ P[k] - MW @ P0[k]).length)
    print("KF 動かした頂点 %d か所（止めた頂点 %d）・一番動いた長さ %.4f" % (len(free), len(fix), mx))
    bm.to_mesh(m); m.update()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
    print("KF 書き出し", OUT)
bm.free()
