# -*- coding: utf-8 -*-
"""踏み込みの瞬間にメッシュが床より下へ沈むぶんだけ、腰（Hips）の高さをなだらかに持ち上げる。
   1コマだけ持ち上げるとガクンと見えるので、必要量の包絡線を滑らかにしてから足す。
   回転は触らない（腰の移動カーブの上下だけ）。
   5番目に down と書くと、逆に「クリップ全体が床から浮いている」ときに下げることも許す。
   生成したばかりのモデルは、歩きが丸ごと数センチ浮いていることがあるため。
   既定（down を書かない）では今までどおり持ち上げるだけで、下げはしない。
   実行: blender -b --factory-startup -P liftdip.py -- 入力.glb 出力.glb クリップ名 [なめらかさ(周期の割合, 既定0.12)] [down]"""
import bpy, sys, json, struct, math
import numpy as np
a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, CLIP = a[0], a[1], a[2]; SMOOTH = float(a[3]) if len(a) > 3 else 0.12
DOWN = (len(a) > 4 and a[4] == 'down')   # 浮いているときに下げることも許すか
N = 64
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE'); mesh = next(o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith('Icosphere'))
if arm.animation_data is None: arm.animation_data_create()
def lowest():
    dg=bpy.context.evaluated_depsgraph_get(); ev=mesh.evaluated_get(dg); me=ev.to_mesh()
    z=min((ev.matrix_world @ v.co).z for v in me.vertices); ev.to_mesh_clear(); return z
# 床＝素の姿勢の最下点
arm.animation_data.action=None; bpy.context.view_layer.update(); floor=lowest()
act=bpy.data.actions.get(CLIP); arm.animation_data.action=act; f0,f1=act.frame_range
fps=bpy.context.scene.render.fps; T=(f1-f0)/fps
need=[]
for k in range(N):
    bpy.context.scene.frame_set(int(round(f0+(f1-f0)*k/N))); bpy.context.view_layer.update()
    d = floor - lowest()               # 正なら沈んでいる、負なら浮いている
    need.append(d if DOWN else max(0.0, d))
need=np.array(need)
# 包絡線をなめらかに：周期的に、幅 SMOOTH の窓で「最大」を取ってからガウスでならす
w=max(1,int(round(SMOOTH*N)))
env=np.array([need[[(k+d)%N for d in range(-w,w+1)]].max() for k in range(N)])
g=np.exp(-0.5*(np.arange(-w,w+1)/(w/2.0))**2); g/=g.sum()
lift=np.array([sum(env[(k+d)%N]*g[d+w] for d in range(-w,w+1)) for k in range(N)])
# ならした結果が必要量を下回るコマが無いように、足りない分は底上げ
lift=np.maximum(lift, need)
print("LD %s 床%.3f 必要量 最大%.3f  持ち上げ 最小%.3f 最大%.3f (身長比 %.1f%%)"%(CLIP,floor,need.max(),lift.min(),lift.max(),lift.max()/1.1*100))
print("LD コマごと必要量: "+" ".join("%.0f"%(x*1000) for x in need[::2])+" (mm)")
print("LD コマごと持ち上げ: "+" ".join("%.0f"%(x*1000) for x in lift[::2])+" (mm)")
# ---- glTF の Hips 移動カーブに足す（Armature のスケール 0.01 を考慮して cm へ） ----
raw=open(SRC,'rb').read(); off=12; ck=[]
while off<len(raw):
    ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
Jm={t:(o,l) for t,o,l in ck}
G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO,BL=Jm[0x004E4942]; bd=bytearray(raw[BO:BO+BL])
NUM={'SCALAR':1,'VEC3':3,'VEC4':4}
def lay(i):
    ac=G['accessors'][i]; n=NUM[ac['type']]; bv=G['bufferViews'][ac['bufferView']]
    return ac,n,bv.get('byteOffset',0)+ac.get('byteOffset',0), bv.get('byteStride') or n*4
def rd(i):
    ac,n,b,st=lay(i); return np.array([struct.unpack_from('<'+'f'*n,bd,b+k*st) for k in range(ac['count'])])
def wr(i,arr):
    ac,n,b,st=lay(i)
    for k in range(ac['count']): struct.pack_into('<'+'f'*n,bd,b+k*st,*arr[k])
nodes=G['nodes']; n2i={nd.get('name',''):i for i,nd in enumerate(nodes)}
parent={}
for i,nd in enumerate(nodes):
    for c in nd.get('children',[]): parent[c]=i
# Hips の親（Armature）のスケールと回転：Y-up の cm 空間なので、ワールドの上向き 1m = 100/scale
pa=parent[n2i['Hips']]; sc=nodes[pa].get('scale',[1,1,1])[1]
an=next(x for x in G['animations'] if x.get('name')==CLIP)
for c in an['channels']:
    if c['target']['node']!=n2i['Hips'] or c['target']['path']!='translation': continue
    s=an['samplers'][c['sampler']]; ti=rd(s['input'])[:,0]; v=rd(s['output'])
    step=3 if s.get('interpolation')=='CUBICSPLINE' else 1
    for k in range(1 if step==3 else 0,len(v),step):
        u=(ti[k//step]/T)%1.0; x=u*N; k0=int(x)%N; k1=(k0+1)%N; f=x-k0
        L=lift[k0]*(1-f)+lift[k1]*f
        v[k,1]+=L/sc
    wr(s['output'],v)
    ac=G['accessors'][s['output']]
    if 'min' in ac: ac['min'][1]=float(v[:,1].min()); ac['max'][1]=float(v[:,1].max())
G['buffers'][0]['byteLength']=len(bd)
js=json.dumps(G,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(bd); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out); print("LD 書き出し",DST)
