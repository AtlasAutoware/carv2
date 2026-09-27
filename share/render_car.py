"""Render the whole car with Blender Cycles from share/scene/ (made by share/car_scene.py).

    python3 -m pip install bpy==4.2.0          (Python 3.11; or run inside Blender 4.2: blender -b -P share/render_car.py -- ...)
    python3 share/render_car.py -- car_front_left car_rear_right [--quick] [--samples 128] [--size 3000x2000]

Views: car_front_left, car_rear_right, car_side, car_top, car_exploded, car_front, bench_stand.
Writes share/<view>.png. The two boards come from their KiCad models (boards/*/out/render/atlas_*.glb, made by
boards/tools/run_kicad.sh glb-drive glb-brain); without them the view renders with no boards.
"""
import json
import math
import os
import sys

import bpy
import mathutils

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE_DIR = os.path.join(HERE, 'scene')
MM = 0.001

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
QUICK = '--quick' in argv
SAMPLES = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else (16 if QUICK else 160)
SIZE = argv[argv.index('--size') + 1] if '--size' in argv else ('900x600' if QUICK else '3000x2000')
W, H = (int(v) for v in SIZE.split('x'))
_vals = {argv[i + 1] for i, a in enumerate(argv) if a in ('--samples', '--size', '--glb-dir', '--light') and i + 1 < len(argv)}
VIEWS = [a for a in argv if not a.startswith('--') and a not in _vals]
GLB_FROM = argv[argv.index('--glb-dir') + 1] if '--glb-dir' in argv else None
LIGHT_SCALE = float(argv[argv.index('--light') + 1]) if '--light' in argv else 1.0

MAN = json.load(open(os.path.join(SCENE_DIR, 'scene.json')))


# ----------------------------------------------------------------------------- materials
def principled(name, base, metallic=0.0, rough=0.5, spec=0.5, coat=0.0, transmission=0.0, ior=1.45, emission=None,
               alpha=1.0, bump=0.0, bump_scale=600.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1.0)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Transmission Weight'].default_value = transmission
    b.inputs['IOR'].default_value = ior
    b.inputs['Alpha'].default_value = alpha
    if emission:
        b.inputs['Emission Color'].default_value = (*emission[0], 1.0)
        b.inputs['Emission Strength'].default_value = emission[1]
    if bump:
        tex = nt.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = bump_scale
        tex.inputs['Detail'].default_value = 4.0
        bn = nt.nodes.new('ShaderNodeBump')
        bn.inputs['Strength'].default_value = bump
        bn.inputs['Distance'].default_value = 0.0002
        nt.links.new(tex.outputs['Fac'], bn.inputs['Height'])
        nt.links.new(bn.outputs['Normal'], b.inputs['Normal'])
    return m


def materials():
    M = {}
    M['petg_cf'] = principled('petg_cf', (0.030, 0.030, 0.034), rough=0.58, spec=0.4, bump=0.25, bump_scale=900.0)
    M['plastic_black'] = principled('plastic_black', (0.018, 0.018, 0.02), rough=0.42, spec=0.45)
    M['plastic_dark'] = principled('plastic_dark', (0.05, 0.05, 0.055), rough=0.5)
    M['rubber'] = principled('rubber', (0.022, 0.022, 0.022), rough=0.82, spec=0.3, bump=0.3, bump_scale=400.0)
    M['rubber_matte'] = principled('rubber_matte', (0.02, 0.02, 0.022), rough=0.7)
    M['rim'] = principled('rim', (0.025, 0.025, 0.028), rough=0.35, spec=0.5, coat=0.2)
    M['steel'] = principled('steel', (0.62, 0.62, 0.64), metallic=1.0, rough=0.28)
    M['steel_black'] = principled('steel_black', (0.05, 0.05, 0.055), metallic=0.9, rough=0.35)
    M['chrome'] = principled('chrome', (0.85, 0.85, 0.87), metallic=1.0, rough=0.08)
    M['spring_steel'] = principled('spring_steel', (0.12, 0.12, 0.13), metallic=1.0, rough=0.35)
    M['alu'] = principled('alu', (0.80, 0.80, 0.82), metallic=1.0, rough=0.3)
    M['alu_dark'] = principled('alu_dark', (0.18, 0.18, 0.2), metallic=1.0, rough=0.32)
    M['motor_can'] = principled('motor_can', (0.30, 0.31, 0.33), metallic=1.0, rough=0.35)
    M['brass'] = principled('brass', (0.78, 0.60, 0.32), metallic=1.0, rough=0.28)
    M['gold'] = principled('gold', (0.95, 0.72, 0.38), metallic=1.0, rough=0.2)
    M['nickel'] = principled('nickel', (0.70, 0.70, 0.68), metallic=1.0, rough=0.22)
    M['anodized_dark'] = principled('anodized_dark', (0.035, 0.035, 0.04), metallic=0.85, rough=0.38)
    M['sensor_grey'] = principled('sensor_grey', (0.16, 0.165, 0.175), metallic=0.6, rough=0.45)
    M['sensor_dark'] = principled('sensor_dark', (0.04, 0.04, 0.045), rough=0.4)
    M['optics_black'] = principled('optics_black', (0.01, 0.01, 0.012), rough=0.05, spec=0.8, coat=1.0)
    M['lens_black'] = principled('lens_black', (0.02, 0.02, 0.022), rough=0.45)
    M['glass'] = principled('glass', (0.55, 0.62, 0.75), rough=0.02, transmission=1.0, ior=1.5)
    M['clear_plastic'] = principled('clear_plastic', (0.85, 0.88, 0.9), rough=0.12, transmission=0.9, ior=1.49)
    M['cable_green'] = principled('cable_green', (0.03, 0.12, 0.07), rough=0.55)
    M['cable_grey'] = principled('cable_grey', (0.10, 0.10, 0.11), rough=0.6)
    M['cable_black'] = principled('cable_black', (0.02, 0.02, 0.02), rough=0.55)
    M['wire_black'] = principled('wire_black', (0.02, 0.02, 0.022), rough=0.5, coat=0.3)
    M['wire_red'] = principled('wire_red', (0.55, 0.02, 0.02), rough=0.45, coat=0.3)
    M['wire_white'] = principled('wire_white', (0.75, 0.75, 0.72), rough=0.5)
    M['wire_grey'] = principled('wire_grey', (0.25, 0.25, 0.26), rough=0.5)
    M['pcb_dark'] = principled('pcb_dark', (0.02, 0.07, 0.04), rough=0.35, coat=0.5)
    M['pcb_black'] = principled('pcb_black', (0.02, 0.02, 0.025), rough=0.35, coat=0.5)
    M['label_white'] = principled('label_white', (0.8, 0.8, 0.78), rough=0.6)
    M['led_green'] = principled('led_green', (0.05, 0.4, 0.1), rough=0.3, emission=((0.1, 1.0, 0.2), 2.0))
    M['noctua_beige'] = principled('noctua_beige', (0.64, 0.52, 0.38), rough=0.5)
    M['noctua_brown'] = principled('noctua_brown', (0.26, 0.13, 0.08), rough=0.45)
    M['cell_wrap'] = principled('cell_wrap', (0.05, 0.15, 0.35), rough=0.3, coat=0.6)
    M['pla_grey'] = principled('pla_grey', (0.35, 0.36, 0.38), rough=0.55, bump=0.2, bump_scale=900.0)
    return M


# ----------------------------------------------------------------------------- scene
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02 if QUICK else 0.012
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 6
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.sample_clamp_indirect = 6.0
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    return sc


def import_stl(path, name):
    bpy.ops.wm.stl_import(filepath=path, global_scale=MM)
    ob = bpy.context.selected_objects[0]
    ob.name = name
    return ob


def smooth(ob, angle=35.0):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    except Exception:
        bpy.ops.object.shade_smooth()


GROUP_OBJS = {}


def add_to_group(group, ob):
    GROUP_OBJS.setdefault(group, []).append(ob)


def build(M):
    sc = bpy.context.scene
    for o in MAN['objects']:
        ob = import_stl(os.path.join(SCENE_DIR, o['file']), o['name'])
        ob.data.materials.clear()
        ob.data.materials.append(M[o['material']])
        smooth(ob, 28.0 if o['material'] in ('petg_cf', 'plastic_black', 'alu', 'pla_grey') else 40.0)
        add_to_group(o['group'], ob)
    for c in MAN['cables']:
        cu = bpy.data.curves.new(c['name'], 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = c['d'] / 2 * MM
        cu.bevel_resolution = 4
        cu.use_fill_caps = True
        sp = cu.splines.new('POLY')
        pts = c['pts']
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (p[0] * MM, p[1] * MM, p[2] * MM, 1.0)
        ob = bpy.data.objects.new('cable_' + c['name'], cu)
        ob.data.materials.append(M[c['material']])
        sc.collection.objects.link(ob)
        add_to_group(c['group'], ob)
    # the boards
    for b, info in MAN['boards'].items():
        glb = os.path.join(os.path.dirname(HERE), info['glb'])
        if GLB_FROM:
            glb = os.path.join(GLB_FROM, os.path.basename(glb))
        if not os.path.exists(glb):
            print('no board model', glb, flush=True)
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=glb)
        new = [o for o in bpy.data.objects if o not in before]
        root = bpy.data.objects.new('board_' + b, None)
        sc.collection.objects.link(root)
        for o in new:
            if o.parent is None:
                o.parent = root
        root.location = tuple(v * MM for v in info['at'])
        add_to_group(b, root)
        bpy.context.view_layer.update()
        mins, maxs = [1e9] * 3, [-1e9] * 3
        for o in new:
            if o.type != 'MESH':
                continue
            for v in o.bound_box:
                w = o.matrix_world @ mathutils.Vector(v)
                for i in range(3):
                    mins[i] = min(mins[i], w[i]); maxs[i] = max(maxs[i], w[i])
        print(b, 'board bbox mm', [round(v / MM, 1) for v in mins], [round(v / MM, 1) for v in maxs], flush=True)


def studio(M):
    sc = bpy.context.scene
    gz = MAN['ground_z'] * MM
    # floor: dark, slightly glossy, fading into the background
    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0, 0, gz))
    fl = bpy.context.active_object
    fl.name = 'floor'
    fm = bpy.data.materials.new('floor')
    fm.use_nodes = True
    nt = fm.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.007, 0.007, 0.009, 1)
    bsdf.inputs['Roughness'].default_value = 0.42
    bsdf.inputs['Specular IOR Level'].default_value = 0.5
    fl.data.materials.append(fm)
    # world: near-black, the site's #030305-ish background
    wd = bpy.data.worlds.new('world')
    sc.world = wd
    wd.use_nodes = True
    wd.node_tree.nodes['Background'].inputs['Color'].default_value = (0.006, 0.006, 0.009, 1)
    wd.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0

    rig = bpy.data.objects.new('light_rig', None)      # the lights turn with the camera, so every view is lit alike
    sc.collection.objects.link(rig)

    def area(name, loc, size, energy, color, target=(0, 0, -0.03)):
        L = bpy.data.lights.new(name, 'AREA')
        L.shape = 'RECTANGLE'
        L.size, L.size_y = size
        L.energy = energy
        L.color = color
        o = bpy.data.objects.new(name, L)
        sc.collection.objects.link(o)
        o.location = loc
        d = mathutils.Vector(target) - mathutils.Vector(loc)
        o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        o.parent = rig
        return o
    k = LIGHT_SCALE
    area('key', (0.9, -1.1, 1.3), (1.4, 1.0), 95.0 * k, (1.0, 0.98, 0.96))
    area('fill', (-1.2, 0.9, 0.7), (1.6, 1.2), 26.0 * k, (0.86, 0.90, 1.0))
    area('top', (0.0, 0.0, 1.8), (1.6, 1.0), 42.0 * k, (1.0, 1.0, 1.0))
    area('rim', (-1.3, -0.4, 0.75), (1.4, 0.4), 16.0 * k, (1.0, 0.35, 0.30), target=(0, 0, 0.04))   # a little of the brand's red
    area('back', (-1.2, 0.9, 1.0), (1.0, 0.6), 30.0 * k, (1.0, 1.0, 1.0))
    area('kick', (1.4, 0.6, 0.15), (0.8, 0.3), 14.0 * k, (1.0, 1.0, 1.0))


def camera(name, az, el, dist, focus, lens=55.0, ortho=None, up_x=False):
    sc = bpy.context.scene
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start = 0.01
    cam.clip_end = 30.0
    if ortho:
        cam.type = 'ORTHO'
        cam.ortho_scale = ortho
    o = bpy.data.objects.new(name, cam)
    sc.collection.objects.link(o)
    a, e = math.radians(az), math.radians(el)
    f = mathutils.Vector(focus)
    o.location = f + mathutils.Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))) * dist
    d = f - o.location
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if up_x:
        o.rotation_euler.rotate_axis('Z', math.radians(90))
    sc.camera = o
    rig = bpy.data.objects.get('light_rig')
    if rig:
        rig.rotation_euler = (0.0, 0.0, 0.0 if el > 80 else math.radians(az + 38.0))
    return o


def set_visible(group_prefixes, visible):
    for g, objs in GROUP_OBJS.items():
        if any(g.startswith(p) for p in group_prefixes):
            for o in objs:
                o.hide_render = not visible
                for ch in o.children_recursive:
                    ch.hide_render = not visible


def lift(groups, dz):
    for g in groups:
        for o in GROUP_OBJS.get(g, []):
            o.location.z += dz * MM


def swing_antennas(deg):
    """Swing both antennas back about their knuckles (they are swivel dipoles). Returns the old matrix."""
    h = MAN.get('antenna_hinge')
    o = bpy.data.objects.get('antennas')
    if not h or o is None:
        return None
    bpy.context.view_layer.update()
    old = o.matrix_world.copy()
    piv = old @ mathutils.Vector((h['x'] * MM, 0.0, h['z'] * MM))
    rot = mathutils.Matrix.Rotation(math.radians(-deg), 4, 'Y')
    o.matrix_world = mathutils.Matrix.Translation(piv) @ rot @ mathutils.Matrix.Translation(-piv) @ old
    return old


def render(view):
    sc = bpy.context.scene
    F = (0.012, 0.0, -0.038)
    set_visible(['chassis', 'deck', 'pack', 'drive', 'brain', 'canopy', 'sensors', 'cable'], True)
    lifts = {}
    folded = None
    if view == 'car_front_left':
        camera(view, -38.0, 13.0, 1.2, F, lens=55)
    elif view == 'car_rear_right':
        camera(view, 222.0, 20.0, 1.18, F, lens=55)
    elif view == 'car_front':
        camera(view, 0.0, 9.0, 1.25, (0.0, 0.0, -0.035), lens=60)
    elif view == 'car_side':
        camera(view, -90.0, 3.0, 1.6, (0.008, 0.0, -0.045), lens=60)
    elif view == 'car_top':
        camera(view, -90.0, 89.9, 1.5, (0.01, 0.0, 0.0), lens=60)
        floor_tone(0.0025, 0.75)
    elif view == 'car_exploded':
        lifts = {'drive': 55, 'brain': 115, 'canopy': 185, 'cable_canopy': 185}
        for g, dz in lifts.items():
            lift([g], dz)
        set_visible(['cable'], False)
        set_visible(['cable_canopy'], False)
        folded = swing_antennas(50.0)      # 75 degrees back in all, so the lifted canopy's antennas stay in frame
        camera(view, -36.0, 20.0, 1.42, (0.012, 0.0, 0.015), lens=55)
    elif view == 'bench_stand':
        pass
    else:
        raise SystemExit('unknown view ' + view)
    sc.render.filepath = os.path.join(HERE, view + ('_quick' if QUICK else '') + '.png')
    bpy.ops.render.render(write_still=True)
    print('wrote', sc.render.filepath, flush=True)
    for g, dz in lifts.items():
        lift([g], -dz)
    if view == 'car_exploded' and folded is not None:
        bpy.data.objects['antennas'].matrix_world = folded
    floor_tone(0.007, 0.42)


def floor_tone(base, rough):
    m = bpy.data.materials.get('floor')
    if m:
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (base, base, base * 1.25, 1)
        b.inputs['Roughness'].default_value = rough


if __name__ == '__main__':
    reset()
    M = materials()
    build(M)
    studio(M)
    for v in VIEWS or ['car_front_left']:
        render(v)
