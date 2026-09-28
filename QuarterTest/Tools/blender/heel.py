import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=a[0])
arm  = next(o for o in bpy.data.objects if o.type=='ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('char'))
act = next((x for x in bpy.data.actions if x.name=='Idle'), None)
if arm.animation_data is None: arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
if act: arm.animation_data.action = act
bpy.context.scene.frame_set(bpy.context.scene.frame_start)
bpy.context.view_layer.update()
gi = {g.name: g.index for g in mesh.vertex_groups}
LG=[gi[n] for n in ("LeftFoot","LeftToeBase") if n in gi]
RG=[gi[n] for n in ("RightFoot","RightToeBase") if n in gi]
side={}
for v in mesh.data.vertices:
    l=sum(g.weight for g in v.groups if g.group in LG); r=sum(g.weight for g in v.groups if g.group in RG)
    if max(l,r)>0.5: side[v.index]='L' if l>r else 'R'
dg=bpy.context.evaluated_depsgraph_get()
me=bpy.data.meshes.new_from_object(mesh.evaluated_get(dg)); mw=mesh.matrix_world
pts=[mw@v.co for v in me.vertices]
z0=min(p.z for p in pts); H=max(p.z for p in pts)-z0
foot=[(i,pts[i]) for i in side if i<len(pts)]
ys=[p.y for _,p in foot]; ymid=(min(ys)+max(ys))/2
def rng(tag, back):
    xs=[p.x for i,p in foot if side[i]==tag and ((p.y<ymid) == back)]
    return (min(xs),max(xs)) if xs else None
for label, back in (("かかと側", True), ("つま先側", False)):
    L=rng('L',back); R=rng('R',back)
    if not L or not R: continue
    if (L[0]+L[1])/2 > (R[0]+R[1])/2: L,R = R,L
    print("HEEL %-8s 左 %.3f〜%.3f  右 %.3f〜%.3f  隙間 %.4f = %.2f%%"
          % (label, L[0],L[1],R[0],R[1], R[0]-L[1], 100*(R[0]-L[1])/H))
