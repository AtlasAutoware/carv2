"""Pictures for posting: the printed kit with both boards on it, rendered with VTK.

    python3 share/make_renders.py --export-meshes      # needs cadquery: the kit as meshes in share/meshes/
    python3 share/make_renders.py [--quick] [--view car_top]
    for v in car_front_left car_rear_right car_exploded car_top; do python3 share/make_renders.py --view $v; done

The kit is built by mech/kit.py (CadQuery) and kept as meshes in share/meshes/, so the pictures can be
rendered on a machine that has VTK (and a GPU) but no CadQuery. The boards come from the GLB files that
`boards/tools/run_kicad.sh glb-drive glb-brain` writes (KiCad's own 3D models, tracks and silkscreen);
without them the kit's plain board outlines stand in. The Jetson module with its heatsink, the NVMe card,
the RJ45 jacks, the stacking header, the lidar and the camera are simple stand-in shapes, not models of
the real parts.

Writes share/car_*.png (3000 x 2000, --quick: 1200 x 800).
"""
import json
import math
import os
import sys

import vtk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MESHES = os.path.join(HERE, 'meshes')

QUICK = '--quick' in sys.argv
SS = 2
W, H = (1200 * SS, 800 * SS) if QUICK else (3000 * SS, 2000 * SS)

GLB = {b: os.path.join(ROOT, 'boards', b, 'out', 'render', f'atlas_{b}.glb') for b in ('drive', 'brain')}


def polydata(shape, tol=0.15):
    shape = shape.val() if hasattr(shape, 'val') else shape
    verts, tris = shape.tessellate(tol, 0.25)
    pts = vtk.vtkPoints()
    for v in verts:
        pts.InsertNextPoint(v.x, v.y, v.z)
    cells = vtk.vtkCellArray()
    for a, b, c in tris:
        cells.InsertNextCell(3)
        cells.InsertCellPoint(a)
        cells.InsertCellPoint(b)
        cells.InsertCellPoint(c)
    pd = vtk.vtkPolyData()
    pd.SetPoints(pts)
    pd.SetPolys(cells)
    nm = vtk.vtkPolyDataNormals()
    nm.SetInputData(pd)
    nm.SetFeatureAngle(40)
    nm.SplittingOn()
    nm.ConsistencyOn()
    nm.Update()
    return nm.GetOutput()


def export_meshes():
    """build the kit with CadQuery and save every part and stand-in as a mesh, with where the boards go"""
    sys.path.insert(0, os.path.join(ROOT, 'mech'))
    import kit  # noqa: E402
    S, comps, parts, extras, info = kit.build()
    os.makedirs(MESHES, exist_ok=True)
    man = {'parts': [], 'comps': []}
    for group, items in (('parts', parts), ('comps', comps)):
        for name, shp in items.items():
            w = vtk.vtkXMLPolyDataWriter()
            w.SetFileName(os.path.join(MESHES, name + '.vtp'))
            w.SetInputData(polydata(shp))
            w.SetDataModeToBinary()
            w.SetCompressorTypeToZLib()
            w.Write()
            man[group].append(name)
    P = kit.P
    zd = P['DRIVE_Z']
    man['place'] = {'drive': [P['DRIVE'][0], P['DRIVE'][2], zd],
                    'brain': [P['BRAIN'][0], P['BRAIN'][2], zd + P['PCB_T'] + P['STACK_H']]}
    json.dump(man, open(os.path.join(MESHES, 'manifest.json'), 'w'), indent=1)
    print('meshes:', len(man['parts']), 'parts and', len(man['comps']), 'stand-ins in', MESHES)


def load_meshes():
    man = json.load(open(os.path.join(MESHES, 'manifest.json')))
    out = {}
    for group in ('parts', 'comps'):
        out[group] = {}
        for name in man[group]:
            r = vtk.vtkXMLPolyDataReader()
            r.SetFileName(os.path.join(MESHES, name + '.vtp'))
            r.Update()
            out[group][name] = r.GetOutput()
    return out['parts'], out['comps'], {k: tuple(v) for k, v in man['place'].items()}


def actor(pd, color, rough=0.55, metal=0.0, opacity=1.0):
    m = vtk.vtkPolyDataMapper()
    m.SetInputData(pd)
    a = vtk.vtkActor()
    a.SetMapper(m)
    p = a.GetProperty()
    p.SetInterpolationToPBR()
    p.SetColor(*color)
    p.SetRoughness(rough)
    p.SetMetallic(metal)
    p.SetOpacity(opacity)
    return a


CF = (0.075, 0.075, 0.085)            # carbon-fibre PETG, matte
ALU = (0.78, 0.79, 0.80)
STANDIN = (0.36, 0.38, 0.42)
SENSOR = (0.85, 0.45, 0.16)
# stand-in shapes a board's own 3D model replaces (the RJ45 jacks, the stacking header, the NVMe card and the
# Jetson module have no 3D model in the board files, so their stand-ins stay)
BOARD_STANDINS = {'drive': ('drive_pcb', 'drive_top_parts', 'drive_bulk_caps', 'usb_c_and_button', 'drive_fets_bottom'),
                  'brain': ('brain_pcb',)}


def scene(explode=0.0):
    """actors for the whole car; explode lifts the brain board (and what sits on it) by 2x and the drive
    board by 1x this many mm"""
    acts = []
    use_glb = {b for b, p in GLB.items() if os.path.exists(p)}
    skip = {n for b in use_glb for n in BOARD_STANDINS[b]}
    for name, pd in PARTS.items():
        acts.append(actor(pd, CF, rough=0.6))
    for name, pd in COMPS.items():
        if name in skip:
            continue
        lift = 0.0
        if name in ('jetson_module_and_sink', 'nvme_2280', 'rj45_poe_camera', 'rj45_lidar', 'brain_pcb', 'brain_standoffs_20mm'):
            lift = 2 * explode
        elif name.startswith(('drive_', 'esc_heatsink', 'usb_c', 'stack_header')):
            lift = explode
        col, rough, metal = STANDIN, 0.5, 0.0
        if name.startswith(('lidar', 'camera', 'tim', 'triton')):
            col = SENSOR
        elif name == 'esc_heatsink':
            col, rough, metal = ALU, 0.35, 1.0
        elif name.startswith('cells'):
            col = (0.25, 0.32, 0.55)
        elif 'standoffs' in name:
            col, rough, metal = (0.8, 0.72, 0.45), 0.35, 1.0
        a = actor(pd, col, rough, metal)
        a.SetPosition(0, 0, lift)
        acts.append(a)
    return acts, use_glb


def add_glb(ren, board, lift):
    """import a board GLB (metres, board-local frame, see run_kicad.sh) into the car frame"""
    imp = vtk.vtkGLTFImporter()
    imp.SetFileName(GLB[board])
    tmp = vtk.vtkRenderWindow()
    tmp.SetOffScreenRendering(1)
    r = vtk.vtkRenderer()
    tmp.AddRenderer(r)
    imp.SetRenderWindow(tmp)
    imp.Update()
    x0, y0, z0 = PLACE[board]
    acts = r.GetActors()
    acts.InitTraversal()
    out = []
    for _ in range(acts.GetNumberOfItems()):
        a = acts.GetNextActor()
        t = vtk.vtkTransform()
        t.PostMultiply()
        if a.GetUserMatrix():
            t.SetMatrix(a.GetUserMatrix())
        t.RotateX(90)                    # glTF is Y-up: the board lies in its XZ plane
        t.Scale(1000, 1000, 1000)
        t.Translate(x0, y0, z0 + lift)
        a.SetUserMatrix(t.GetMatrix())
        ren.AddActor(a)
        out.append(a)
    return out


_KEEP = []


def render(path, cam_pos, focal, up=(0, 0, 1), explode=0.0, angle=26.0):
    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.SetSize(W, H)
    ren = vtk.vtkRenderer()
    rw.AddRenderer(ren)
    ren.GradientBackgroundOn()
    ren.SetBackground(0.012, 0.012, 0.02)          # brand dark #030305 at the bottom
    ren.SetBackground2(0.10, 0.10, 0.13)
    acts, use_glb = scene(explode)
    for a in acts:
        ren.AddActor(a)
    if 'drive' in use_glb:
        add_glb(ren, 'drive', explode)
    if 'brain' in use_glb:
        add_glb(ren, 'brain', 2 * explode)
    ren.RemoveAllLights()
    for pos, col, inten in (((600, -500, 900), (1.0, 0.97, 0.92), 1.8),      # key, front right, high
                            ((-700, 600, 500), (0.75, 0.82, 1.0), 0.8),       # fill, rear left
                            ((-200, -900, 250), (1.0, 0.35, 0.3), 0.6),       # red rim, the brand accent
                            ((0, 0, 1200), (1.0, 1.0, 1.0), 0.9),             # top
                            ((900, 300, 200), (1.0, 1.0, 1.0), 0.5)):         # low side
        L = vtk.vtkLight()
        L.SetLightTypeToSceneLight()
        L.SetPosition(*pos)
        L.SetFocalPoint(*focal)
        L.SetColor(*col)
        L.SetIntensity(inten)
        ren.AddLight(L)
    cam = ren.GetActiveCamera()
    cam.SetPosition(*cam_pos)
    cam.SetFocalPoint(*focal)
    cam.SetViewUp(*up)
    cam.SetViewAngle(angle)
    ren.ResetCameraClippingRange()
    rw.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.ReadFrontBufferOff()
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetFileName(path)
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.Write()
    # rendered at twice the size and scaled down: the anti-aliasing (VTK's FXAA and SSAO passes do not
    # work on the software OpenGL this runs on)
    from PIL import Image
    Image.open(path).convert('RGB').resize((W // SS, H // SS), Image.LANCZOS).save(path, optimize=True)
    print('wrote', path, '(board models: %s)' % (', '.join(sorted(use_glb)) or 'none, outlines only'), flush=True)
    _KEEP.append((rw, ren, w2i))     # freed at return, the window takes minutes to tear down: keep it


if __name__ == '__main__':
    if '--export-meshes' in sys.argv:
        export_meshes()
        sys.exit(0)
    PARTS, COMPS, PLACE = load_meshes()
    F = (20, -25, 20)
    r = 820
    only = sys.argv[sys.argv.index('--view') + 1] if '--view' in sys.argv else None
    for name, az, el, ex in (('car_front_left', -40, 28, 0), ('car_rear_right', 140, 30, 0),
                             ('car_exploded', -35, 30, 45), ('car_top', -90, 89, 0)):
        if only and name != only:
            continue
        a, e = math.radians(az), math.radians(el)
        pos = (F[0] + r * math.cos(e) * math.cos(a), F[1] + r * math.cos(e) * math.sin(a), F[2] + r * math.sin(e))
        up = (1, 0, 0) if el > 80 else (0, 0, 1)
        render(os.path.join(HERE, name + '.png'), pos, F if not ex else (F[0], F[1], F[2] + 40), up, ex)
    # tearing down the software-OpenGL windows with both board models loaded takes longer than the
    # rendering, and a second view in the same process runs slowly after the first: one view per
    # process (--view) is quickest, and the process ends here without any teardown
    sys.stdout.flush()
    os._exit(0)
