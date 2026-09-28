# -*- coding: utf-8 -*-
"""すでに着せてある部品を、あとから大きさ・位置・向きだけ調整する。

   wearsolo.py は部品を「新しく着せる」道具なので、一度着せたものを微調整するには使えない。
   dressup.html のスライダーで決めた値は、今のモデルに対する差分なので、
   最初から着せ直すと数字が合わない。この道具はスライダーとまったく同じ計算をする。

   順番は dressup.html と同じ「回す→拡大縮小→ずらす」。基準は部品の外接箱の中心。
   靴のように左右で分けたいときは「左右別」を渡す。x>0 が左足、x<0 が右足。

   部品は材質の名前「種類:名前」で探す。

   「丈」は上下だけの縮尺。基準は部品のてっぺん（服なら襟）なので、肩の位置は動かさず
   すそだけが上がる。横幅は変わらない。dressup.html の「丈」スライダーと同じ計算。

   実行: blender -b --factory-startup -P tunepart.py --
         入力.glb 出力.glb 種類 大きさ ずらしx,y,z（cm）
         [回転x,y,z（度）既定0,0,0] [左右別 Lx,Ly,Lz;Rx,Ry,Rz（cm）] [丈 既定1.0] [横幅 既定1.0] [奥行き 既定1.0]
         [肩の角度（度）既定0] [袖の穴を絞る 既定0]
   「肩の角度」は襟より外を、外へ離れた距離に応じて下げる（＋）か上げる（−）。上から35%の高さまで効く。
   「袖の穴を絞る」は穴のまわりの頂点を穴の中心へ寄せる。dressup.html の % を 100 で割った値（1.0 で 100%）。
   「横幅」は左右（x）だけ、「奥行き」は前後（y）だけの縮尺。部品の中心を基準に両側へ広がる。
   dressup.html の「横幅」「奥行き」と同じ。
   例:   ... -- doll.glb out.glb hair 0.95 -2.0,-4.0,-4.0
         ... -- doll.glb out.glb cloth 1.0 0,0,0 "" "" 0.70
         ... -- doll.glb out.glb pants 1.0 0,0,0 "" "" 0.80 1.10
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Matrix, Vector

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, KIND = a[0], a[1], a[2]
S = float(a[3])
D = [float(v)/100.0 for v in a[4].split(',')]                      # cm で受けて m にする
R = [float(v) for v in a[5].split(',')] if len(a) > 5 and a[5] else [0.0, 0.0, 0.0]
SIDE = [[float(v)/100.0 for v in g.split(',')] for g in a[6].split(';')] if len(a) > 6 and a[6] else None
HEM = float(a[7]) if len(a) > 7 and a[7] else 1.0                   # 丈（上下だけの縮尺）
WID = float(a[8]) if len(a) > 8 and a[8] else 1.0                   # 横幅（左右だけの縮尺。中心基準）
DEP = float(a[9]) if len(a) > 9 and a[9] else 1.0                   # 奥行き（前後だけの縮尺。中心基準）
SHO = float(a[10]) if len(a) > 10 and a[10] else 0.0                # 肩の角度（度。＋で肩を下げる）
HOLE = float(a[11]) if len(a) > 11 and a[11] else 0.0               # 袖の穴を絞る（0〜1.5。dressup.html の % ÷100）

def find_armholes(P, halfW, ztop, zbot):
    """袖の穴を探す（dressup.html の findArmholes と同じ）。
       両脇（半幅の55%より外）の上半分の点を、横から見た平面（前後 y × 上下 z）の 5mm の升に落とし、
       空いていて上下左右に埋まった升がある所を空き地とし、いちばん大きいつながった空き地を穴とする。
       返すのは [(側の符号, 穴の中心 y, 穴の中心 z, 半径)]"""
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
        print("TP 袖の穴 %s: 中心 y %.3f z %.3f  半径 %.1f cm（升 %d）" % ("左" if sgn > 0 else "右", hy, hz, R*100, len(best)))
    return out

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm and arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()

def kind_of(o):
    for m in o.data.materials:
        if m and ':' in m.name: return m.name.split(':')[0]
    return ''

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
part = next((o for o in meshes if kind_of(o) == KIND), None)
if part is None:
    print("TP 種類 %s の部品が無い。あるのは %s" % (KIND, [(o.name, kind_of(o)) for o in meshes]))
    sys.exit(1)
mesh = part.data
print("TP %s（頂点 %d）  大きさ %.3f  丈 %.3f  ずらし %s cm  回転 %s 度"
      % (part.name, len(mesh.vertices), S, HEM, [v*100 for v in D], R))

# dressup.html と同じ向き。Blender は Z が上、three.js は Y が上なので、
# 「つま先を上下」は Blender の X、「左右に回す」は Blender の Z、「左右に傾ける」は Blender の Y
rot = None
if any(R):
    rot = (Matrix.Rotation(math.radians(R[0]), 4, 'X')
           @ Matrix.Rotation(math.radians(R[2]), 4, 'Z')
           @ Matrix.Rotation(math.radians(R[1]), 4, 'Y'))

# 計算は world 座標でやる。部品の入れ物には縮尺が掛かっていることがあり
# （この髪は1/100だった）、メッシュの座標のまま cm を足すと、100分の1しか動かない。
MW = part.matrix_world
MWI = MW.inverted()
WP = {v.index: (MW @ v.co) for v in mesh.vertices}

groups = [(None, D)] if not SIDE else [(1, SIDE[0]), (-1, SIDE[1] if len(SIDE) > 1 else SIDE[0])]
for sgn, d in groups:
    idx = [v.index for v in mesh.vertices] if sgn is None else \
          [i for i, w in WP.items() if (w.x > 0) == (sgn > 0)]
    if not idx: continue
    P = np.array([tuple(WP[i]) for i in idx])
    c = Vector(tuple((P.min(0) + P.max(0)) / 2))
    topT = c.z + (P[:,2].max() - c.z) * S + d[2]       # 動かしたあとのてっぺん。丈の基準
    # 肩の角度で使う。動かしたあとのすそ・高さ・襟の半幅（半幅の35%）・中心x。dressup.html と同じ式
    botT = topT - (topT - (c.z + (P[:,2].min() - c.z) * S + d[2])) * HEM
    Hp = max(1e-6, topT - botT)
    x0 = 0.35 * (P[:,0].max() - P[:,0].min()) / 2 * S * WID
    cxT = c.x + d[0]
    tanA = math.tan(math.radians(SHO)) if SHO else 0.0
    halfW = (P[:,0].max() - P[:,0].min()) / 2
    holes = find_armholes(P, halfW, P[:,2].max(), P[:,2].min()) if HOLE else []
    for i in idx:
        w = WP[i]
        if holes and abs(w.x) > 0.35*halfW:
            # 袖の穴を絞る。穴の中心へ、中心に近いほど強く寄せる（dressup.html と同じ式）。元の座標で先に掛ける
            for hsg, hy, hz, R in holes:           # 外の sgn（左右別の側）を潰さないよう別名にする
                if (w.x > 0) != (hsg > 0): continue
                dy_, dz_ = w.y - hy, w.z - hz; dd = math.hypot(dy_, dz_); Ro = R*2.2
                if dd < Ro:
                    f = max(0.1, 1 - HOLE*(1 - dd/Ro))
                    w = Vector((w.x, hy + dy_*f, hz + dz_*f))
        p = w - c
        if rot: p = rot @ p
        q = p * S
        q.x *= WID                                      # 横幅。X だけに掛ける（dressup.html と同じ）
        q.y *= DEP                                      # 奥行き。Blender の Y（前後）だけに掛ける
        q = c + q + Vector(tuple(d))
        if HEM != 1.0: q.z = topT - (topT - q.z) * HEM  # 丈。てっぺんを動かさずに上下だけ縮める
        if tanA:
            # 襟より外の頂点だけを、外へ離れた距離×tan(角度) だけ下げる。上から35%までで効き、下へ行くほど弱まる
            ex = abs(q.x - cxT) - x0
            t = (q.z - (topT - 0.35*Hp)) / (0.35*Hp)
            if ex > 0 and t > 0: q.z -= tanA * ex * min(1.0, t)
        mesh.vertices[i].co = MWI @ q
    nm = "全体" if sgn is None else ("左（x>0）" if sgn > 0 else "右（x<0）")
    print("TP %s: 頂点 %d  中心 (%.3f, %.3f, %.3f)  丈の基準の高さ %.3f"
          % (nm, len(idx), c.x, c.y, c.z, topT))

Q = np.array([tuple(part.matrix_world @ v.co) for v in mesh.vertices])
print("TP 動かしたあと: x %.3f〜%.3f  y %.3f〜%.3f  z %.3f〜%.3f"
      % (Q[:,0].min(), Q[:,0].max(), Q[:,1].min(), Q[:,1].max(), Q[:,2].min(), Q[:,2].max()))

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True, export_image_format='JPEG', export_jpeg_quality=92)
print("TP 書き出し", DST, os.path.getsize(DST))
