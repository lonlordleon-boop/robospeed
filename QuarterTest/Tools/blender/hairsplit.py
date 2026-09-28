# -*- coding: utf-8 -*-
"""首より下で、髪と服（肌）のつなぎ目を切り離す。面は消さない（つながった頂点を 2 つに分けるだけ）。骨・動きはそのまま。
   お嬢様（小学生編）は、肩に乗った髪と肩の服が生成でつながっていた。髪は頭、服は腕で動くので、つなぎ目がどうしても伸び、
   重みをならしても肩の上で 5〜10cm 引き伸ばされた（「肩にまだ髪が付いてる」）。止まっている時は同じ位置なのですき間はできない。
   動いた時に見える髪の内側は、キャラクターツールが面の裏も描くので透けない。
   1) 面を「髪」と「それ以外」に分ける：面の真ん中の色が暗い（明るさ < 0.5）面、と肩の上の白い切れ端
      （肩の箱の中・高さ ≥ SLZ・白・頭の重みの最大 ≥ 0.5。髪の中に入り込んだ布。髪の側に入れて髪の色に塗る）
   2) 髪の面とそれ以外の面の両方が付いた頂点（高さ ZLO〜首+3cm）を 2 つに分ける（辺だけでなく点で触れている所も）。
      点だけで触れていた服の頂点は、まわりの服の頂点へなめらかに寄せる（生成でできたへこみを直す）
   3) 重み：髪の側（首より下）は腕の骨（Shoulder・Arm・ForeArm・Hand）を外す。服の側（首より下・肌以外）は頭の重みを外す。
      外して何も残らない頂点は、同じ側でいちばん近い頂点の重みを写す
      同じ位置の頂点（絵の切れ目）も、髪の側と服の側で別々の重みにする＝絵の切れ目でも切り離す
   4) 首より下の髪どうしの重みを NIT 回ならす（髪の側だけ）
   実行: blender -b --factory-startup -P hairsplit.py -- 入力.glb 出力.glb [--paint 元の絵.png 出力.png] [--slz 0.795] [--zlo 0.55] [--nit 12]
   肩の箱は腕の骨の根元から決める（左右それぞれ |x| が関節の ±9cm、高さ 0.72〜首+3cm、前後 −0.03〜+0.08m）"""
import bpy, bmesh, sys, colorsys, numpy as np
from mathutils import kdtree
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, n=1, default=None):
    global a
    if name in a:
        i = a.index(name); v = a[i+1:i+1+n]; a = a[:i] + a[i+1+n:]; return v if n > 1 else v[0]
    return default
PAINT = opt('--paint', 2); SLZ = float(opt('--slz', 1, 0.795)); ZLO = float(opt('--zlo', 1, 0.55)); NIT = int(opt('--nit', 1, 12))
SRC, OUT = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
gi = {g.index: g.name for g in me.vertex_groups}; gn = {g.name: g.index for g in me.vertex_groups}
MW = me.matrix_world
def bh(n): return arm.matrix_world @ arm.data.bones[n].head_local
# 分ける高さの上は首 +8cm。+3cm では、肩の上の後ろ寄り・首に近い所（0.84〜0.89m）で服と髪のつながりが残り、
# 腕を上げると白いトゲが髪へ伸びた（お嬢様 5 回目）
zN = bh('neck').z; ZHI = zN + 0.08
JL, JR = bh('LeftArm'), bh('RightArm')
def inshoulder(c):
    return any(abs(c[0] - J.x) <= 0.09 and 0.72 <= c[2] <= ZHI and -0.03 <= c[1] <= 0.08 for J in (JL, JR))
HEAD = gn['Head']
ARMG = {gn[s + b] for s in ('Left', 'Right') for b in ('Shoulder', 'Arm', 'ForeArm', 'Hand') if s + b in gn}
ARMS = {s: {gn[s + b] for b in ('Shoulder', 'Arm', 'ForeArm', 'Hand') if s + b in gn} for s in ('Left', 'Right')}
bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
uvL = bm.loops.layers.uv.active; dfL = bm.verts.layers.deform.active
def fcol(f):
    uv = np.mean([l[uvL].uv[:] for l in f.loops], 0)
    return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])
def wc(f): return MW @ f.calc_center_median()
hairF = set(); sliver = []
for f in bm.faces:
    h, s, v = fcol(f)
    if v < 0.5: hairF.add(f.index); continue
    c = wc(f)
    if s < 0.12 and c.z >= SLZ and inshoulder(c) and max(vv[dfL].get(HEAD, 0.0) for vv in f.verts) >= 0.5:
        hairF.add(f.index); sliver.append(f.index)
print("HS 髪の面 %d（うち肩の上の白い切れ端 %d）" % (len(hairF), len(sliver)))
# 切れ端を髪の色で塗る（面の中だけ。まわりへは広げない：袖の面にはみ出して黒いギザギザが出た）
if PAINT and sliver:
    im0 = bpy.data.images.load(PAINT[0]); TW, TH = im0.size; tp = np.array(im0.pixels[:], np.float32).reshape(TH, TW, 4)
    M = np.zeros((TH, TW), bool)
    for fi in sliver:
        uv = [l[uvL].uv[:] for l in bm.faces[fi].loops]
        for k in range(1, len(uv) - 1):
            tri = np.array([uv[0], uv[k], uv[k+1]]) * [TW, TH]
            x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
            x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, TW - 1); y1 = min(y1, TH - 1)
            if x1 < x0 or y1 < y0: continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = tri
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-12: continue
            l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
            l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
            M[y0:y1 + 1, x0:x1 + 1] |= (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02)
    rgb = tp[:, :, :3]
    # 髪の色：髪の面の画素の中央値（明るさ < 0.3）
    hc = []
    for f in bm.faces:
        if f.index in hairF and f.index not in sliver and len(hc) < 4000:
            c = wc(f)
            if inshoulder(c):
                uv = np.mean([l[uvL].uv[:] for l in f.loops], 0); p = tp[int(np.clip(uv[1], 0, .9999) * TH), int(np.clip(uv[0], 0, .9999) * TW), :3]
                if p.max() < 0.3: hc.append(p)
    col = np.median(np.array(hc), 0); out = tp.copy(); out[M, :3] = col
    im = bpy.data.images.new("o", TW, TH, alpha=True); im.pixels = out.ravel(); im.filepath_raw = PAINT[1]; im.file_format = 'PNG'; im.save()
    print("HS 切れ端を髪の色 %s で %d 画素塗った → %s" % (np.round(col * 255).astype(int), int(M.sum()), PAINT[1]))
# 2) つなぎ目の頂点を分ける：髪の面とそれ以外の面の両方が付いた頂点（高さ ZLO〜首+3cm）を 2 つにし、髪の面は新しい頂点を使う。
#    辺だけ分ける（split_edges）と、点だけで触れている所が残った。右袖の前の頂点 1 つが前髪の房の先と点でつながり、
#    頭の重みのまま袖にへこみを作っていた
tag = bm.faces.layers.int.new("hair")
for f in bm.faces: f[tag] = 1 if f.index in hairF else 0
rip = [v for v in bm.verts if ZLO <= (MW @ v.co).z <= ZHI and len({f[tag] for f in v.link_faces}) == 2]
loopL = [bm.loops.layers.uv[k] for k in range(len(bm.loops.layers.uv))]
nrip = 0; clothB = set()
for v in rip:
    # 服の面に囲まれ、髪とは辺を 1 本も共有しない頂点（点だけで触れていた）だけを、あとで寄せる
    point_only = not any(len({f[tag] for f in e.link_faces}) == 2 for e in v.link_edges)
    nv = bm.verts.new(v.co, v)                      # 頂点の情報（重み）ごと写す
    for f in [f for f in v.link_faces if f[tag] == 1]:
        vs = [nv if x == v else x for x in f.verts]
        uvs = [[l[L].uv.copy() for L in loopL] for l in f.loops]
        nf = bm.faces.new(vs, f)
        for l, u in zip(nf.loops, uvs):
            for L, uu in zip(loopL, u): l[L].uv = uu
        bm.faces.remove(f)
    nrip += 1
    if point_only: clothB.add(v)
print("HS 分けた頂点 %d（うち点だけで触れていた頂点 %d）" % (nrip, len(clothB)))
bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
# 分けた服の側の頂点を、まわりの服の頂点へなめらかに寄せる（へこみを直す。3 回、半分ずつ）
for _ in range(3):
    newp = {}
    for v in clothB:
        ns = [e.other_vert(v) for e in v.link_edges if all(f[tag] == 0 for f in e.link_faces)]
        if len(ns) >= 2: newp[v] = v.co * 0.5 + sum((x.co for x in ns), v.co * 0) / len(ns) * 0.5
    for v, p in newp.items(): v.co = p
bm.verts.index_update(); bm.faces.index_update()
# 3) 側ごとの重み
side = {}
for v in bm.verts:
    t = {f[tag] for f in v.link_faces}
    side[v.index] = 'H' if t == {1} else ('C' if t == {0} else 'M')
P = [MW @ v.co for v in bm.verts]
def skinV(v):   # 肌（首の肌は頭と動いてよい）：まわりの面の多数が肌色
    k = [(0.02 < h < 0.11 and s >= 0.12) for h, s, _ in (fcol(f) for f in v.link_faces)]
    return sum(k) * 2 > len(k)
fixH = []; fixC = []; pulled = []
# 重みは「同じ位置の頂点（絵の切れ目）」の側ごとにまとめて決め、全員に同じ値を入れる。
# 頂点 1 つずつ決めたら、切れ目の片方だけ頭の重みが外れて、頭が動くと顎の下の継ぎ目が開き、穴になった（お嬢様 6 回目）
def renorm(w):
    s_ = sum(w.values()); return {g: x / s_ for g, x in w.items()} if s_ > 1e-3 else {}
def setw(ids, w):
    for i in ids:
        dv = bm.verts[i][dfL]
        for g in list(dv.keys()): del dv[g]
        for g, x in w.items(): dv[g] = x
posg = {}
for v in bm.verts: posg.setdefault(tuple(np.round(np.array(P[v.index]), 5)), []).append(v.index)
for ids in posg.values():
    p = P[ids[0]]
    Hs = [i for i in ids if side[i] == 'H']; Cs = [i for i in ids if side[i] == 'C']
    # 髪は高さに関係なく腕で動かさない（首より上の髪にも腕の重みが残っていて、腕を上げると髪のかけらが散った）
    if Hs and ZLO <= p.z:
        w = dict(bm.verts[Hs[0]][dfL].items())
        if any(g in ARMG for g in w):
            w = renorm({g: x for g, x in w.items() if g not in ARMG})
            if w: setw(Hs, w)
            else: fixH += Hs
    if not Cs or not (ZLO <= p.z <= ZHI): continue
    if any(skinV(bm.verts[i]) for i in Cs): continue        # 肌（首・顎）は触らない
    # 首より上で真ん中寄り（顎の下・首の前）は触らない。服の側で直すのは首より下と、肩（|x| > 8cm）だけ
    if p.z >= zN and abs(p.x) <= 0.08: continue
    w = dict(bm.verts[Cs[0]][dfL].items())
    if abs(p.x) > 0.03:
        # 服の反対側の腕の重みを外す（右肩の服に左腕 0.26 が付いていて、左腕を上げると右肩が引っ張られた）
        other = ARMS['Right' if p.x > 0 else 'Left']
        if any(g in other for g in w): w = renorm({g: x for g, x in w.items() if g not in other}) or w
    if w.get(HEAD, 0) > 0:
        if w.get(HEAD, 0) >= 0.5: pulled += Cs                # 髪に引き寄せられた服の頂点（下でまわりから決める）
        w2 = renorm({g: x for g, x in w.items() if g != HEAD})
        if not w2: fixC += Cs; continue
        w = w2
    setw(Cs, w)
def copy_near(fix, sd):
    src = [v.index for v in bm.verts if side[v.index] == sd and v.index not in set(fix) and sum(v[dfL].values()) > 1e-3 and ZLO - 0.05 <= P[v.index].z <= ZHI + 0.05]
    kd = kdtree.KDTree(len(src))
    for n, i in enumerate(src): kd.insert(P[i], n)
    kd.balance()
    for i in fix:
        j = src[kd.find(P[i])[1]]; dv = bm.verts[i][dfL]
        for g, w in bm.verts[j][dfL].items(): dv[g] = w
copy_near(fixH, 'H'); copy_near(fixC, 'C')
print("HS 髪の側から腕の重みを外した（残らず写した頂点 %d）・服の側から頭の重みを外した（写した頂点 %d）" % (len(fixH), len(fixC)))
# 髪に引き寄せられた服の頂点（頭の重み ≥ 0.5 だった）：生成で髪の房の先とつながり、袖にへこみを作っていた（右袖の前）。
# 重みはまわりの服の頂点の平均、位置もまわりへ半分ずつ 3 回寄せる。同じ位置の頂点（絵の切れ目）はまとめて動かす
grp = {}
for i in pulled: grp.setdefault(tuple(np.round(np.array(P[i]), 5)), []).append(i)
ps = set(pulled); moved = 0.0
for _ in range(3):
    upd = {}
    for k, ids in grp.items():
        ns = {e.other_vert(bm.verts[i]).index for i in ids for e in bm.verts[i].link_edges} - ps
        ns = [j for j in ns if side.get(j) == 'C']
        if len(ns) < 2: continue
        co = sum((bm.verts[j].co for j in ns), bm.verts[ids[0]].co * 0) / len(ns)
        w = {}
        for j in ns:
            for g, x in bm.verts[j][dfL].items(): w[g] = w.get(g, 0) + x / len(ns)
        upd[k] = (bm.verts[ids[0]].co * 0.5 + co * 0.5, w)
    for k, (co, w) in upd.items():
        for i in grp[k]:
            moved = max(moved, (bm.verts[i].co - co).length)
            bm.verts[i].co = co; dv = bm.verts[i][dfL]
            for g in list(dv.keys()): del dv[g]
            for g, x in w.items(): dv[g] = x
print("HS 髪に引き寄せられた服の頂点 %d（位置 %d か所）をまわりに合わせた" % (len(pulled), len(grp)))
# 4) 首より下の髪どうしをならす（同じ位置の髪の頂点はまとめる）
hv = [v.index for v in bm.verts if side[v.index] == 'H' and ZLO <= P[v.index].z < zN]
key = {}; canon = {}
for i in hv: canon[i] = key.setdefault(tuple(np.round(np.array(P[i]), 5)), i)
nb = {}
hs = set(hv)
for e in bm.edges:
    i, j = e.verts[0].index, e.verts[1].index
    if i in hs and j in hs and canon[i] != canon[j]:
        nb.setdefault(canon[i], set()).add(canon[j]); nb.setdefault(canon[j], set()).add(canon[i])
G = len(me.vertex_groups); C = sorted(set(canon.values()))
Wt = {c: np.zeros(G) for c in C}
for c in C:
    for g, w in bm.verts[c][dfL].items(): Wt[c][g] = w
def jump(): return max((np.abs(Wt[x] - Wt[y]).sum() for x in C for y in nb.get(x, ())), default=0)
j0 = jump()
for _ in range(NIT):
    new = {x: 0.5 * Wt[x] + 0.5 * np.mean([Wt[y] for y in nb[x]], 0) for x in C if nb.get(x)}
    Wt.update(new)
print("HS 首より下の髪 %d 頂点：となりとの差の最大 %.2f → %.2f" % (len(C), j0, jump()))
for i in hv:
    w = Wt[canon[i]].copy(); top = np.argsort(-w)[:4]; keep = np.zeros_like(w); keep[top] = w[top]
    keep[keep < 0.01] = 0; keep /= max(keep.sum(), 1e-9)
    dv = bm.verts[i][dfL]
    for g in list(dv.keys()): del dv[g]
    for g in np.nonzero(keep)[0]: dv[int(g)] = float(keep[g])
bm.faces.layers.int.remove(tag)
bm.to_mesh(m); bm.free(); m.update()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("HS 書き出し", OUT)
