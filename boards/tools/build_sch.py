"""python3 build_sch.py drive|brain  -> writes the KiCad schematic and parts JSON for a board."""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eda  # noqa: E402

board = sys.argv[1]
spec = importlib.util.spec_from_file_location('design', os.path.join(HERE, '..', board, 'design.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
d = mod.d
out = os.path.join(HERE, '..', board)
bad = d.check()
for net, nodes in bad:
    print('WARNING single-pin net', net, nodes)
root, sheets = eda.write_schematic(d, out, project=d.name)
eda.export_json(d, os.path.join(out, d.name + '_parts.json'), root)
n = eda.write_symbol_lib(d, os.path.join(out, 'atlas.kicad_sym'))
eda.write_project_files(out, d.name)
eda.write_kicad_pro(out, d.name)
print('custom symbols', n)
print(board, len(d.parts), 'parts,', len(d.nets()), 'nets,', len(sheets), 'sheets')
