"""Print the pads of KiCad footprints: python3 fpinfo.py Lib:Name [Lib:Name ...]  (host python, no KiCad needed)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, find, find1, uq  # noqa: E402

FPDIR = os.environ.get('KICAD_FP_DIR', os.path.expanduser(
    '~/.local/share/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints'))
LOCAL = {'atlas': os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib', 'atlas.pretty')}


def pads(fpid):
    lib, name = fpid.split(':')
    path = os.path.join(LOCAL.get(lib, os.path.join(FPDIR, lib + '.pretty')), name + '.kicad_mod')
    root = parse(open(path).read())[0]
    out = []
    for p in find(root, 'pad'):
        at = find1(p, 'at')
        sz = find1(p, 'size')
        out.append((uq(p[1]), p[2], p[3], float(at[1]), float(at[2]), float(sz[1]), float(sz[2])))
    return out


if __name__ == '__main__':
    for fpid in sys.argv[1:]:
        try:
            ps = pads(fpid)
        except Exception as e:
            print('==', fpid, 'ERROR', e)
            continue
        print('==', fpid, len(ps), 'pads')
        for p in ps:
            print('   %-4s %-8s %-8s at (%7.3f, %7.3f) size %.3f x %.3f' % p)
