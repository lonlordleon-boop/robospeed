# -*- coding: utf-8 -*-
"""袖の穴を面でふさぐ。

   シャツの網は外側と内側の二重の袋で縁が無く、袖の穴は袋を貫くトンネル。
   dressup.html の「袖の穴を絞る」は縁を中心へ寄せるだけなので、絞りきっても小さな穴が残る。
   ふさぐには面を足すしかない。この道具は穴の縁の輪を見つけ、中心から扇形に面を張る。

   絵の付け方が要。足した面に元の縁の絵をそのまま使うと、縁の頂点は別々の島に散らばっているので、
   扇の三角形が島と島のあいだの絵を引き伸ばして汚れる。
   だから新しい頂点を作り、絵はいちばん大きい島（胴）の一列から取る。
   その島で「高さ z と絵の縦位置 v」の関係を直線で合わせておき、扇の頂点の高さから v を決める。
   横位置 u は島のまん中で固定。縞が横向きなら、扇にも同じ高さに同じ色の縞が出る。

   重みは縁のいちばん近い頂点から写す。
   穴の探し方は tunepart.py の find_armholes と同じ。

   実行: blender -b --factory-startup -P capholes.py -- 入力.glb 出力.glb [種類 既定cloth] [扇の分割数 既定36]
"""
import bpy, sys, os, math, bmesh
import numpy as np
from mathutils import Vector, kdtree

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
KIND = a[2] if len(a) > 2 else 'cloth'
NSEG = int(a[3]) if len(a) > 3 else 36

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm and arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()

part = next(o for o in bpy.data.objects if o.type == 'MESH'
            and any(m and m.name.startswith(KIND + ':') for m in o.data.materials))
mesh = part.data
MW = part.matrix_world; MWI = MW.inverted()
P = np.array([tuple(MW @ v.co) for v in mesh.vertices])
halfW = (P[:,0].max() - P[:,0].min()) / 2
print("CH %s 頂点 %d  x %.3f〜%.3f  z %.3f〜%.3f" % (part.name, len(P), P[:,0].min(), P[:,0].max(), P[:,2].min(), P[:,2].max()))

def find_armholes(P, halfW, ztop, zbot):
    CELL = 0.005; out = []
    zmid = zbot + 0.5*(ztop - zbot)
    for sgn in (1, -1):
        occ = set(); cmin = {}; cmax = {}; rmin = {}; rmax = {}
        for x, y, z in P:
            if (x > 0) != (sgn > 0) or abs(x) < 0.55*halfW or z < zmid: continue
            iy, iz = int(round(y/CELL)), int(round(z/CELL))
            occ.add((iy, iz))
            cmin[iy] = min(cmin.get(iy, iz), iz); cmax[iy] = max(cmax.get(iy, iz), iz)
            rmin[iz] = min(rmin.get(iz, iy), iy); rmax[iz] = max(rmax.get(iz, iy), iy)
        empty = set()
        for iy, z0 in cmin.items():
            z1 = cmax[iy]
            for iz in range(z0, z1+1):
                if (iy, iz) in occ or iz not in rmin: continue
                if rmin[iz] < iy < rmax[iz] and z0 < iz < z1: empty.add((iy, iz))
        seen = set(); best = None
        for k in empty:
            if k in seen: continue
            st = [k]; seen.add(k); cells = []
            while st:
                q = st.pop(); cells.append(q)
                for dy_, dz_ in ((1,0),(-1,0),(0,1),(0,-1)):
                    n = (q[0]+dy_, q[1]+dz_)
                    if n in empty and n not in seen: seen.add(n); st.append(n)
            if best is None or len(cells) > len(best): best = cells
        if not best or len(best) < 4: continue
        hy = sum(q[0] for q in best)/len(best)*CELL; hz = sum(q[1] for q in best)/len(best)*CELL
        R = math.sqrt(len(best)*CELL*CELL/math.pi)
        out.append((sgn, hy, hz, R))
        print("CH 袖の穴 %s: 中心 y %.3f z %.3f  半径 %.1f cm" % ("左" if sgn > 0 else "右", hy, hz, R*100))
    return out

holes = find_armholes(P, halfW, P[:,2].max(), P[:,2].min())
if not holes:
    print("CH 穴が見つからない"); sys.exit(1)

# ---- 絵の取り方を決める。いちばん大きい島で「高さ z ↔ 絵の縦 v（または横 u）」を直線で合わせる ----
uvl = mesh.uv_layers[0].data
par = list(range(len(mesh.loops))); key = {}
def find(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
def uni(x, y):
    x, y = find(x), find(y)
    if x != y: par[y] = x
for li in range(len(mesh.loops)):
    k = (round(uvl[li].uv[0], 5), round(uvl[li].uv[1], 5))
    if k in key: uni(key[k], li)
    else: key[k] = li
for poly in mesh.polygons:
    ls = list(poly.loop_indices)
    for l in ls[1:]: uni(ls[0], l)
area = {}
for poly in mesh.polygons:
    ls = list(poly.loop_indices)
    q = [np.array(uvl[i].uv) for i in ls[:3]]
    r = find(ls[0]); area[r] = area.get(r, 0.0) + abs(np.cross(q[1]-q[0], q[2]-q[0]))/2
big = max(area, key=area.get)
U, V, Z = [], [], []
for li, lp in enumerate(mesh.loops):
    if find(li) != big: continue
    U.append(uvl[li].uv[0]); V.append(uvl[li].uv[1]); Z.append(P[lp.vertex_index][2])
U, V, Z = np.array(U), np.array(V), np.array(Z)
# z とよく揃う軸を選ぶ（相関の絶対値が大きいほう）
cu = abs(np.corrcoef(U, Z)[0,1]) if U.std() > 1e-9 else 0
cv = abs(np.corrcoef(V, Z)[0,1]) if V.std() > 1e-9 else 0
axis_v = cv >= cu
T = V if axis_v else U
A = np.vstack([T, np.ones_like(T)]).T
(a_, b_), res, _, _ = np.linalg.lstsq(A, Z, rcond=None)
rms = float(np.sqrt(np.mean((A @ np.array([a_, b_]) - Z)**2)))
other = U if axis_v else V
umid = float(np.median(other))
print("CH 絵の島（最大）: ループ %d  z は %s と揃う（相関 u %.2f / v %.2f）  z = %.3f*t + %.3f  ずれ %.1f mm  固定する側 %.3f"
      % (len(T), "v" if axis_v else "u", cu, cv, a_, b_, rms*1000, umid))
def uv_of_z(z):
    t = (z - b_) / a_ if abs(a_) > 1e-9 else T.mean()
    t = min(T.max(), max(T.min(), t))
    return (umid, t) if axis_v else (t, umid)

# ---- 縁の輪を見つけて扇を張る ----
bm = bmesh.new(); bm.from_mesh(mesh)
bm.verts.ensure_lookup_table()
OV = list(bm.verts)                      # 頂点を足すと番号表が古くなるので、元の頂点は先に控えておく
uv_layer = bm.loops.layers.uv.verify()
dl = bm.verts.layers.deform.verify()
kd = kdtree.KDTree(len(P))
for i, p in enumerate(P): kd.insert(Vector(tuple(p)), i)
kd.balance()
added = 0
for sgn, hy, hz, R in holes:
    # 縁＝穴のまわり（半径の 0.85〜1.4 倍）で脇（半幅の 60% より外）にある点。角度ごとに中心へいちばん近いものを取る
    bins = [None] * NSEG
    for i, (x, y, z) in enumerate(P):
        if (x > 0) != (sgn > 0) or abs(x) < 0.6*halfW: continue
        d = math.hypot(y - hy, z - hz)
        if d < 0.85*R or d > 1.4*R: continue
        ang = math.atan2(z - hz, y - hy)
        b = int(((ang + math.pi) / (2*math.pi)) * NSEG) % NSEG
        if bins[b] is None or d < bins[b][0]: bins[b] = (d, i)
    rim = [b_[1] for b_ in bins if b_ is not None]
    if len(rim) < 8:
        print("CH %s: 縁が %d 点しか取れない。飛ばす" % ("左" if sgn > 0 else "右", len(rim))); continue
    # 角度順に並べる
    rim.sort(key=lambda i: math.atan2(P[i][2] - hz, P[i][1] - hy))
    xc = float(np.mean([P[i][0] for i in rim]))
    # 縁の少し内側（穴の中心へ 15%）に新しい頂点を作る。元の縁と同じ所に置くと深さの取り合いでちらつく
    newv = []
    for i in rim:
        y, z = P[i][1], P[i][2]
        py, pz = hy + (y - hy)*0.85, hz + (z - hz)*0.85
        v = bm.verts.new(MWI @ Vector((P[i][0], py, pz)))
        dv = v[dl]                                   # BMDeformVert は辞書を代入できないので1本ずつ写す
        for k, w in OV[i][dl].items(): dv[k] = w
        newv.append((v, pz))
    vc = bm.verts.new(MWI @ Vector((xc, hy, hz)))
    _, ci, _ = kd.find(Vector((xc, hy, hz)))
    dvc = vc[dl]
    for k, w in OV[ci][dl].items(): dvc[k] = w
    n = len(newv)
    for k in range(n):
        v1, z1 = newv[k]; v2, z2 = newv[(k+1) % n]
        try:
            f = bm.faces.new((vc, v1, v2)) if sgn > 0 else bm.faces.new((vc, v2, v1))
        except ValueError:
            continue
        f.material_index = 0
        for lp in f.loops:
            zz = {vc: hz, v1: z1, v2: z2}[lp.vert]
            lp[uv_layer].uv = uv_of_z(zz)
        added += 1
    print("CH %s: 縁 %d 点、扇 %d 枚を張った（中心 x %.3f）" % ("左" if sgn > 0 else "右", n, added, xc))
bm.to_mesh(mesh); bm.free()
mesh.update()
print("CH 足した面 %d" % added)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True, export_image_format='JPEG', export_jpeg_quality=92)
print("CH 書き出し", DST, os.path.getsize(DST))
