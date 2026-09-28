# -*- coding: utf-8 -*-
"""袖ぐりにふさいだ「扇」を、素体の表面の内側へ沈める。

   capholes.py は穴の縁から中心へ平らな扇を張って穴をふさいだ。穴は閉じたが、
   その扇が腕の外側に出てしまい、折った紙皿を袖ぐりに詰めたように見えていた。
   走ると腕と扇が入れ違って、放射状の三角形がそのまま表に出る。

   扇そのものは要る（無いと袖ぐりから服の内側が見える）。要らないのは「腕より外にいること」。
   だから扇の頂点を、いちばん近い素体の面へ移し、そこからさらに内側へ押し込む。
   すると扇は縁から腕の表面までを塞ぐ輪になり、腕にすっぽり隠れる。
   腕が無い所（肩の上）でも、いちばん近い面は肩の皮膚なので、そこで塞がる。

   扇の頂点だけを選ぶ: 穴の中心から測った半径が「縁の半径 × 割合」より内側にあるもの。
   実際に測ると、扇は中心の1点（UVの継ぎ目で36個に割れている）と半径 3〜4cm の輪でできていて、
   服そのものの頂点は 4cm より外にある。割合 0.8（＝4.2cm）でちょうど切り分けられる。
   縁そのもの（元からある服の頂点）は動かさない。
   割合を大きくしすぎると服の脇まで巻き込んで形が崩れる。0.9 でそれをやって失敗した。

   当たり判定も座標も world で通す。素体の入れ物には 1/100 の縮尺が掛かっていて、
   local のまま距離や法線を足すと 100分の1 しか動かない。

   実行: blender -b --factory-startup -P capsink.py --
         入力.glb 出力.glb [種類 既定cloth] [押し込む深さ m 既定0.004] [半径の割合 既定0.8]
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
KIND = a[2] if len(a) > 2 else 'cloth'
DEEP = float(a[3]) if len(a) > 3 else 0.004
FRAC = float(a[4]) if len(a) > 4 else 0.8

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm and arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()

part = next(o for o in bpy.data.objects if o.type == 'MESH'
            and any(m and m.name.startswith(KIND + ':') for m in o.data.materials))
body = bpy.data.objects['body']
mesh = part.data
MW = part.matrix_world; MWI = MW.inverted()
P = np.array([tuple(MW @ v.co) for v in mesh.vertices])
halfW = (P[:,0].max() - P[:,0].min()) / 2
print("CS %s 頂点 %d  x %.3f〜%.3f" % (part.name, len(P), P[:,0].min(), P[:,0].max()))

def find_armholes(P, halfW, ztop, zbot):
    """capholes.py と同じ探し方。穴の中心と半径を返す"""
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
        print("CS 袖の穴 %s: 中心 y %.3f z %.3f  半径 %.1f cm" % ("左" if sgn > 0 else "右", hy, hz, R*100))
    return out

holes = find_armholes(P, halfW, P[:,2].max(), P[:,2].min())
if not holes:
    print("CS 穴が見つからない"); sys.exit(1)

# 素体の面の当たり判定。world 座標で作る（入れ物の縮尺に巻き込まれないように）
BMW = body.matrix_world
bverts = [BMW @ v.co for v in body.data.vertices]
bpolys = [tuple(p.vertices) for p in body.data.polygons]
bvh = BVHTree.FromPolygons(bverts, bpolys)

moved = 0; far = 0
for sgn, hy, hz, R in holes:
    idx = [i for i in range(len(P))
           if (P[i][0] > 0) == (sgn > 0) and abs(P[i][0]) > 0.5*halfW
           and math.hypot(P[i][1]-hy, P[i][2]-hz) < FRAC*R]
    if not idx:
        print("CS %s: 扇の頂点が見つからない" % ("左" if sgn > 0 else "右")); continue
    d = []
    for i in idx:
        # 素体のいちばん近い面へ移し、そこからさらに内側（素体の面の向きと逆）へ押し込む
        loc, nrm, fi, dist = bvh.find_nearest(Vector(tuple(P[i])))
        if loc is None: far += 1; continue
        mesh.vertices[i].co = MWI @ (loc - nrm * DEEP)
        d.append(dist); moved += 1
    # 扇は腕の骨ひとつにくくる。
    # 素体から写した重みのままだと扇は胴に付いていくので、腕を振ったとたん腕が扇から抜け、
    # 放射状の三角形がそのまま表に出る（走りでそうなった）。腕に結べば、いつでも腕の中に隠れる。
    bone = ('LeftArm' if sgn > 0 else 'RightArm')
    vg = part.vertex_groups.get(bone) or part.vertex_groups.new(name=bone)
    for i in idx:
        for g in part.vertex_groups:
            if g.name != bone:
                try: g.remove([i])
                except Exception: pass
        vg.add([i], 1.0, 'REPLACE')
    print("CS %s: 扇を %s の骨ひとつに結んだ" % ("左" if sgn > 0 else "右", bone))
    if d:
        print("CS %s: 扇の頂点 %d 個を素体の面へ移した（もとの距離 平均 %.1f mm、最大 %.1f mm）"
              % ("左" if sgn > 0 else "右", len(d), 1000*np.mean(d), 1000*np.max(d)))
print("CS 動かした頂点 %d（素体の面が見つからなかった %d）" % (moved, far))

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True, export_image_format='JPEG', export_jpeg_quality=92)
print("CS 書き出し", DST, os.path.getsize(DST))
