# -*- coding: utf-8 -*-
"""指定した点のまわりの髪の頂点を、となりの髪の頂点の平均へ少しずつ寄せて、とがった細い面（針）をならす。
   面は消さない。骨・重み・動き・絵はそのまま、髪の頂点の位置だけ。
   お嬢様（小学生編）は、肩の上（高さ 0.80m・左右 0.13m）で、生成で髪と肩の服がつながっていた所の先に、
   細い面が放射状に集まった毛先の束があり、肩と髪の境目に細い毛先が見えた。hairsplit.py で髪の側に入れたあとにかける。
   1) 髪の頂点：まわりの面がすべて暗い（面の真ん中の明るさ < 0.5）
   2) 中心から R 以内の髪の頂点を、となりの髪の頂点の平均へ半分ずつ NIT 回寄せる。
      中心から離れるほど寄せ方を弱める（R で 0。まわりの髪となめらかにつながる）
   中心は、箱の中の細長い面（長さ/幅 ≥ 8）の真ん中の平均で自動で決める（--auto）か、x,y,z で与える
   --cloth で服の頂点（まわりの面がすべて明るい）をならす（お嬢様の右袖の折れ目：-0.1,-0.055,0.76 --r 0.04）
   --collapse --fan x0,x1,y0,y1,z0,z1 で、箱の中の横に寝た髪の板も縮める（お嬢様の右肩：-0.17,-0.095,0.0,0.035,0.805,0.84）
   実行: blender -b --factory-startup -P hairrelax.py -- 入力.glb 出力.glb [--auto] [--cloth] [--collapse [--fan 箱]] [x,y,z ...] [--r 0.025] [--nit 10]"""
import bpy, bmesh, sys, colorsys, numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index("--")+1:]
def opt(name, default):
    global a
    if name in a: i = a.index(name); v = a[i+1]; a = a[:i] + a[i+2:]; return v
    return default
R = float(opt('--r', 0.025)); NIT = int(opt('--nit', 10))
AUTO = '--auto' in a
if AUTO: a.remove('--auto')
# --cloth：髪でなく服の頂点（まわりの面がすべて明るい）をならす。右袖の前に、生成でできた大きな平らな三角の折れ目があった
CLOTH = '--cloth' in a
if CLOTH: a.remove('--cloth')
# --collapse：肩の上の箱の中の細長い暗い面（針：長さ ≥ 2cm・長さ/幅 ≥ 8）を見つけ、そのまわりの髪の頂点を針の根元の方へ横に縮める
#   （下で、根元へ向けて横に縮める）。お嬢様は元の白い切れ端が針の形のまま髪の側に残り、ツールで肩のうしろに灰色の毛先が見えた
COLLAPSE = '--collapse' in a
if COLLAPSE: a.remove('--collapse')
# --fan x0,x1,y0,y1,z0,z1：--collapse で、箱の中の、横（左右）に寝た暗い細長い面（一番長い辺が左右向き ≥ 0.85・長さ ≥ 1.5cm・長さ/幅 ≥ 3）も縮める。
#   お嬢様の右肩は、針を縮めたあとも、そのとなりの少し幅の広い髪の板（首の付け根から腕の方へ横に寝ていた）が櫛の歯のように並び、
#   ツールで横・斜めうしろから見ると、歯の間の白い服が「白いかけら」に見えた。左肩にも同じ形の面があるが、見た目はきれいなので右だけ
FANBOX = tuple(map(float, opt('--fan', '').split(','))) if '--fan' in a else None
SRC, OUT = a[0], a[1]
CEN = [Vector(tuple(map(float, s.split(',')))) for s in a[2:]]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC); bpy.context.view_layer.update()
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
anim = bool(arm.animation_data and arm.animation_data.nla_tracks)
me = next(o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')); m = me.data
img = next(n.image for n in me.active_material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
W_, H_ = img.size; px = np.array(img.pixels[:], np.float32).reshape(H_, W_, 4)
MW = me.matrix_world; MI = MW.inverted()
bm = bmesh.new(); bm.from_mesh(m); uvL = bm.loops.layers.uv.active
def dark(f):
    uv = np.mean([l[uvL].uv[:] for l in f.loops], 0)
    return colorsys.rgb_to_hsv(*px[int(np.clip(uv[1], 0, .9999) * H_), int(np.clip(uv[0], 0, .9999) * W_), :3])[2] < 0.5
DK = {f.index: dark(f) for f in bm.faces}
if AUTO:
    # 肩の上の箱（左右）で、細長い暗い面の真ん中の平均
    for sg in (1, -1):
        cs = []
        for f in bm.faces:
            if not DK[f.index] or len(f.verts) != 3: continue
            c = MW @ f.calc_center_median()
            if not (0.10 <= sg * c.x <= 0.17 and -0.01 <= c.y <= 0.05 and 0.78 <= c.z <= 0.83): continue
            p = [MW @ v.co for v in f.verts]; e = [(p[1]-p[0]).length, (p[2]-p[1]).length, (p[0]-p[2]).length]
            area = (p[1]-p[0]).cross(p[2]-p[0]).length / 2; L = max(e)
            if area > 0 and L / (2 * area / L) >= 8: cs.append(c)
        if cs: CEN.append(sum(cs, Vector()) / len(cs))
print("HR 中心", [tuple(round(x, 3) for x in c) for c in CEN])
if COLLAPSE:
    from mathutils import kdtree
    dfl = bm.verts.layers.deform.active; HEADI = me.vertex_groups['Head'].index
    def needle(f):
        # 暗い面か、頭で動く面（全頂点の頭の重み ≥ 0.9。髪の側に残った白い切れ端）
        if len(f.verts) != 3: return False
        if not DK[f.index] and not all(v[dfl].get(HEADI, 0.0) >= 0.9 for v in f.verts): return False
        c = MW @ f.calc_center_median()
        # 範囲は肩の上。広げたら（|x| 0.09〜0.18・長さ/幅 ≥ 6）普通の髪の房 209 面まで縮めて、肩の髪がギザギザに削れた
        if not (0.10 <= abs(c.x) <= 0.17 and -0.01 <= c.y <= 0.05 and 0.79 <= c.z <= 0.84): return False
        p = [MW @ v.co for v in f.verts]; e = [(p[1]-p[0]).length, (p[2]-p[1]).length, (p[0]-p[2]).length]
        area = (p[1]-p[0]).cross(p[2]-p[0]).length / 2; L = max(e)
        return L >= 0.02 and (area <= 1e-12 or L / (2 * area / L) >= 8)
    NF = [f for f in bm.faces if needle(f)]
    if FANBOX:
        def fan(f):
            if len(f.verts) != 3 or not DK[f.index]: return False
            c = MW @ f.calc_center_median()
            if not (FANBOX[0] <= c.x <= FANBOX[1] and FANBOX[2] <= c.y <= FANBOX[3] and FANBOX[4] <= c.z <= FANBOX[5]): return False
            p = [MW @ v.co for v in f.verts]; E = [p[1]-p[0], p[2]-p[1], p[0]-p[2]]; Lv = max(E, key=lambda e: e.length); L = Lv.length
            area = (p[1]-p[0]).cross(p[2]-p[0]).length / 2
            return L >= 0.015 and abs(Lv.x) / L >= 0.85 and (area <= 1e-12 or L / (2 * area / L) >= 3)
        # 針は前の版で縮め済み。もう一度拾うと左肩の頂点まで動いたので、--fan のときは板だけ縮める
        FF = [f for f in bm.faces if fan(f)]
        print("HR 横に寝た髪の板 %d" % len(FF)); NF = FF
    NV = {v for f in NF for v in f.verts}
    print("HR 針の面 %d" % len(NF))
    # 針は首の近く（|x| 0.10〜0.11）の根元から肩の外（0.145〜0.151）の先まで扇形に集まっていて、先は先の小さな面とつながる。
    # 一番近い髪の頂点へ寄せても先は動かなかった → 針の面の頂点を、根元の x へ向けて横に縮める（長さを SQ 倍に）。
    # 箱の中の髪の頂点をまとめて縮めたら、肩の所で髪が削れたように見えた（「削った感じが出ている」）→ 針の面の頂点だけ動かす。
    # 同じ位置の頂点（絵の切れ目）は一緒に動かす（片方だけ動かすと継ぎ目が開いて穴になる）
    # 3 割の長さに縮めたら、ほぼ真横から見える細い面が光って白い線に見えた → 最後まで縮める（長さ 0）
    SQ = 0.0; MI = MW.inverted()
    posk = {}
    for v in bm.verts: posk.setdefault(tuple(round(x, 6) for x in v.co), []).append(v)
    keys = {tuple(round(x, 6) for x in v.co): (MW @ v.co) for v in NV}      # 動かす前の位置でまとめる（左右とも先に控える）
    for sg in (1, -1):
        base = [MW @ v.co for f in NF for v in f.verts if sg * (MW @ v.co).x < 0.12 and sg * (MW @ v.co).x > 0]
        if not base: continue
        bx = sum(p.x for p in base) / len(base); n = 0
        for k, p in keys.items():
            if sg * (p.x - bx) <= 0: continue
            q = p.copy(); q.x = bx + (p.x - bx) * SQ; co = MI @ q
            for u in posk[k]: u.co = co
            n += 1
        print("HR 針の根元 x=%.3f へ、針の頂点 %d か所を横に縮めた" % (bx, n))
    CEN = []
hv = [v for v in bm.verts if v.link_faces and all((not DK[f.index]) if CLOTH else DK[f.index] for f in v.link_faces)]
W = {}
for v in hv:
    if not CEN: break
    p = MW @ v.co; d = min((p - c).length for c in CEN)
    if d < R: W[v] = 1.0 - d / R
hs = set(hv); moved = 0.0
for _ in range(NIT):
    newp = {}
    for v, w in W.items():
        ns = [e.other_vert(v) for e in v.link_edges if e.other_vert(v) in hs]
        if ns: newp[v] = v.co.lerp(sum((x.co for x in ns), Vector()) / len(ns), 0.5 * w)
    for v, p in newp.items(): v.co = p
print("HR 寄せた髪の頂点 %d" % len(W))
bm.to_mesh(m); bm.free(); m.update()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_animations=anim, **({'export_animation_mode': 'NLA_TRACKS'} if anim else {}), export_skins=True, export_yup=True)
print("HR 書き出し", OUT)
