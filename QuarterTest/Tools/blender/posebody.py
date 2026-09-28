# -*- coding: utf-8 -*-
"""素体だけの腕と脚の開きを、メッシュに焼き込む（服や髪は動かさない）。

   spread_arms.py / spread_legs.py は骨そのものを回すので、同じ骨に結んである服や髪も一緒に動く。
   こちらは骨に触らず、素体のメッシュの「結んだときの形」だけを曲げる。
   だから、服を動かさずに素体の腕だけを袖の中へ収める、といった合わせができる。
   dressup.html の「素体の姿勢（手動）」と同じ計算なので、あそこで決めた角度をそのまま渡せる。

   回す量は、その頂点が腕（または脚）の骨にどれだけ結ばれているかで決める。
   肩から先ほど強く効き、胴は動かない。軸は「前を向く向き」（Head から headfront、上下は捨てる）。
   足首は逆向きに同じだけ回して、靴の裏を水平に戻す。

   骨は動かないので、アニメも重みもそのまま使える。
   ただし歩いたときに腕が曲がる中心は元の骨のままなので、大きく回すほど動きが不自然になる。
   20度前後までのつもりで使う。

   「腕を前に振る角度」は、横向きの軸（前を向く軸と上下の軸に直角）のまわりに、左右いっしょに回す。
   生成された素体は腕が後ろへ流れていることがあり（この素体は約14度）、それを前へ戻すために使う。

   「手首をそろえる」に L または R と書くと、その側の手の向きを左右反転して反対の手へ写す。
   生成された素体は片方の手首だけ折れていることがある（この素体は右手）。
   手首の関節を中心に、手の頂点の重心が向く向きだけを合わせるので、指の形は変わらない。

   実行: blender -b --factory-startup -P posebody.py -- 入力.glb 出力.glb 腕の開き 脚の開き
         [腕を前に振る角度 既定0] [手首をそろえる L か R、既定なし] [メッシュ名 既定body]
   例:   ... -- doll.glb doll_p.glb 21 4 14 L
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector, Quaternion

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST = a[0], a[1]
ARM = float(a[2]) if len(a) > 2 else 0.0
LEG = float(a[3]) if len(a) > 3 else 0.0
SWING = float(a[4]) if len(a) > 4 else 0.0   # 腕を前に振る角度（正で前）
WRIST = a[5].upper() if len(a) > 5 and a[5] else ''   # 'L' か 'R'。その手の向きを反対側へ写す
ARMSYM = a[6].upper() if len(a) > 6 and a[6] else ''  # 'L' か 'R'。その腕の向きを反対側へ写す
NAME = a[7] if len(a) > 7 else 'body'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()
body = next((o for o in bpy.data.objects if o.type == 'MESH' and o.name == NAME), None) \
       or next(o for o in bpy.data.objects if o.type == 'MESH')
mesh = body.data
print("PB %s 頂点 %d  腕 %.1f度  脚 %.1f度" % (body.name, len(mesh.vertices), ARM, LEG))

def branch(name):
    """その骨から下にぶら下がっている骨の名前をぜんぶ返す"""
    b = arm.data.bones.get(name)
    if b is None: return set()
    out = set()
    def walk(x):
        out.add(x.name)
        for c in x.children: walk(c)
    walk(b)
    return out

gi = {g.name: g.index for g in body.vertex_groups}
def weights(names):
    """頂点ごとに、その骨たちに結ばれている重みの合計"""
    idx = set(gi[n] for n in names if n in gi)
    w = np.zeros(len(mesh.vertices))
    for v in mesh.vertices:
        w[v.index] = sum(g.weight for g in v.groups if g.group in idx)
    return np.clip(w, 0.0, 1.0)

W = {
    'handL': weights(branch('LeftHand')), 'handR': weights(branch('RightHand')),
    'armL': weights(branch('LeftArm')),   'armR': weights(branch('RightArm')),
    'legL': weights(branch('LeftUpLeg')), 'legR': weights(branch('RightUpLeg')),
    'ftL':  weights(branch('LeftFoot')),  'ftR':  weights(branch('RightFoot')),
}
for k, v in W.items(): print("PB %s に結ばれた頂点 %d 個" % (k, int((v > 1e-4).sum())))

def head(name):
    b = arm.data.bones.get(name)
    return (arm.matrix_world @ b.head_local) if b else None

P = {'handL': head('LeftHand'), 'handR': head('RightHand'),
     'armL': head('LeftArm'), 'armR': head('RightArm'),
     'legL': head('LeftUpLeg'), 'legR': head('RightUpLeg'),
     'ftL': head('LeftFoot'),  'ftR': head('RightFoot')}
hd, hf = head('Head'), head('headfront')
# Blender では Z が上。前を向く向きは上下（Z）を捨てて水平に寝かせる
if hd and hf:
    AX = Vector((hf.x - hd.x, hf.y - hd.y, 0.0))
    AX = AX.normalized() if AX.length > 1e-9 else Vector((0.0, -1.0, 0.0))
else:
    AX = Vector((0.0, -1.0, 0.0))
print("PB 前を向く軸 (%.3f, %.3f, %.3f)" % (AX.x, AX.y, AX.z))
# 横向きの軸。この軸のまわりに回すと腕が前後に振れる。左右いっしょに同じ向きへ回す
SX = Vector((0.0, 0.0, 1.0)).cross(AX).normalized()
print("PB 横向きの軸 (%.3f, %.3f, %.3f)" % (SX.x, SX.y, SX.z))

MW = body.matrix_world
MWI = MW.inverted()

# 手首をそろえる。手の頂点の重心が手首から見てどちらを向いているかだけを比べ、
# 良いほうの向きを左右反転して悪いほうへ写す回転を求める。指の形はそのまま
def centroid(key):
    w = W[key]; idx = np.where(w > 0.5)[0]
    if len(idx) < 10: return None
    pts = [MW @ mesh.vertices[int(i)].co for i in idx]
    return sum(pts, Vector()) / len(pts)

# 腕をそろえる。骨は左右対称でも、生成されたメッシュは片方だけ後ろへ流れていることがある。
# 肩の関節から見て腕の肉の重心がどちらを向いているかを比べ、良いほうの向きを左右反転して写す。
AQ = None
if ARMSYM in ('L', 'R') and P['armL'] and P['armR']:
    s2, d2 = ('armL', 'armR') if ARMSYM == 'L' else ('armR', 'armL')
    cs2, cd2 = centroid(s2), centroid(d2)
    if cs2 and cd2:
        vs2 = (cs2 - P[s2]).normalized()
        vm2 = Vector((-vs2.x, vs2.y, vs2.z))
        vd2 = (cd2 - P[d2]).normalized()
        q = vd2.rotation_difference(vm2)
        if q.angle > 1e-3:
            AQ = (d2, q)
            print("PB 腕をそろえる: %s の向き (%.2f, %.2f, %.2f) を %s の反転 (%.2f, %.2f, %.2f) へ %.1f度 回す"
                  % (d2, vd2.x, vd2.y, vd2.z, s2, vm2.x, vm2.y, vm2.z, math.degrees(q.angle)))
        else:
            print("PB 腕はもうそろっている")

WQ = None
if WRIST in ('L', 'R') and P['handL'] and P['handR']:
    src, dst = ('handL', 'handR') if WRIST == 'L' else ('handR', 'handL')
    def frame(key):
        """手の「伸びる向き」と「手のひらの広がる向き」の二本を返す。
           向きだけでは手のひらのひねりが分からず、差が2.6度しか出なかった"""
        w = W[key]; idx = np.where(w > 0.5)[0]
        if len(idx) < 10: return None
        pts = np.array([tuple(MW @ mesh.vertices[int(i)].co) for i in idx])
        c = Vector(tuple(pts.mean(axis=0)))
        a_ = (c - P[key]).normalized()
        A = np.array(a_)
        Q = pts - pts.mean(axis=0)
        Q = Q - np.outer(Q @ A, A)                  # 伸びる向きの成分を抜く
        if len(Q) < 3: return None
        _, _, vt = np.linalg.svd(Q, full_matrices=False)
        b_ = Vector(tuple(vt[0])).normalized()      # 一番広がっている向き＝手のひらの幅
        return a_, b_, c
    fs, fd = frame(src), frame(dst)
    if fs and fd:
        (as_, bs_, _), (ad_, bd_, _) = fs, fd
        am = Vector((-as_.x, as_.y, as_.z)); bm = Vector((-bs_.x, bs_.y, bs_.z))
        if bd_.dot(bm) < 0: bm = -bm                # 広がる向きは符号が決まらないので近いほうに合わせる
        q1 = ad_.rotation_difference(am)            # まず伸びる向きを合わせる
        q2 = (q1 @ bd_).rotation_difference(bm)     # 次にその軸まわりのひねりを合わせる
        q = q2 @ q1
        if q.angle > 1e-3:
            WQ = (dst, q)
            print("PB 手首をそろえる: %s を %.1f度 回す（伸びる向きで %.1f度、ひねりで %.1f度）"
                  % (dst, math.degrees(q.angle), math.degrees(q1.angle), math.degrees(q2.angle)))
        else:
            print("PB 手首はもうそろっている")

moved = 0
for v in mesh.vertices:
    p = MW @ v.co
    p0 = p.copy()
    # 先に左右をそろえてから、開きや振りを上乗せする
    for corr in (AQ, WQ):
        if corr is None: continue
        key, q = corr
        w = W[key][v.index]
        if w > 1e-4:
            qq = Quaternion(q.axis, q.angle * w)
            p = (qq @ (p - P[key])) + P[key]
    for key, deg in (('armL', +ARM), ('armR', -ARM),
                     ('legL', +LEG), ('legR', -LEG),
                     ('ftL',  -LEG), ('ftR',  +LEG)):   # 足首は逆に回して靴の裏を水平に保つ
        w = W[key][v.index]
        if w <= 1e-4 or deg == 0.0 or P[key] is None: continue
        q = Quaternion(AX, math.radians(deg) * w)
        p = (q @ (p - P[key])) + P[key]
    # 腕を前後に振る。左右とも同じ向きに回すので符号は分けない
    if SWING != 0.0:
        for key in ('armL', 'armR'):
            w = W[key][v.index]
            if w <= 1e-4 or P[key] is None: continue
            q = Quaternion(SX, math.radians(-SWING) * w)
            p = (q @ (p - P[key])) + P[key]
    if (p - p0).length > 1e-6:
        v.co = MWI @ p; moved += 1
print("PB 動かした頂点 %d" % moved)

bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True,
                          export_morph=True)
print("PB 書き出し", DST, os.path.getsize(DST))
