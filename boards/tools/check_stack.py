"""Check the two boards of the stack against boards/stack/stack.py, from their placements (no KiCad needed).

    python3 check_stack.py

- every pin of the 2 x 20 connector carries the net stack.py gives it, on both boards
- the pins land where stack.py says (drive-local on the drive board, brain X = drive X - 20)
- the brain board's four corner holes sit over drive board holes
Prints one line per problem and a summary; exits 1 if anything is off.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'stack'))
import stack  # noqa: E402

TOL = 0.1           # mm, pin position
HOLE_TOL = 0.2      # mm, brain hole over drive hole


def load(board):
    d = os.path.join(HERE, '..', board)
    name = 'atlas_' + board
    place = json.load(open(os.path.join(d, 'out', name + '_placement.json')))
    lib = json.load(open(os.path.join(d, 'out', 'fp_lib.json')))
    parts = {p['ref']: p for p in json.load(open(os.path.join(d, name + '_parts.json')))['parts']}
    return place, lib, parts


def pad_centres(place, lib, parts, ref):
    """board-local centre of every pad: R(rot) * (M_y on the bottom) * local, as in placer.py"""
    pl = place[ref]
    a = math.radians(pl['rot'])
    c, s = round(math.cos(a)), round(math.sin(a))
    out = {}
    for num, b, drill in lib[parts[ref]['footprint']]['pads']:
        px, py = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if pl['side'] == 'B':
            py = -py
        out[num] = (pl['x'] + px * c - py * s, pl['y'] + px * s + py * c)
    return out


def holes(place, parts):
    return {r: (p['x'], p['y']) for r, p in place.items()
            if parts.get(r, {}).get('footprint', '').startswith('MountingHole:')}


def main():
    bad = []
    boards = {b: load(b) for b in ('drive', 'brain')}
    want_net = {'drive': stack.drive_nets(), 'brain': stack.brain_nets()}
    want_xy = {'drive': stack.pin_xy_drive, 'brain': stack.pin_xy_brain}
    for b, (place, lib, parts) in boards.items():
        pads = pad_centres(place, lib, parts, 'J1001')
        nets = parts['J1001']['pads']
        for n in sorted(stack.PINS):
            got = nets.get(str(n))
            if got != want_net[b][n]:
                bad.append(f'{b} J1001 pin {n}: net {got}, stack.py says {want_net[b][n]}')
            x, y = pads[str(n)]
            wx, wy = want_xy[b](n)
            if math.hypot(x - wx, y - wy) > TOL:
                bad.append(f'{b} J1001 pin {n} at ({x:.2f}, {y:.2f}), stack.py says ({wx:.2f}, {wy:.2f})')
    # the brain board's corner holes over drive board holes
    dh = holes(boards['drive'][0], boards['drive'][2])
    bh = holes(boards['brain'][0], boards['brain'][2])
    # plus the two corner spacers kept from Antmicro's board (do-not-fit now, the holes stay)
    sys.path.insert(0, os.path.join(HERE, '..', 'brain'))
    import fork_config
    keep = set(sum(fork_config.DNP_REFS.values(), []))
    obst = json.load(open(os.path.join(HERE, '..', 'brain', 'out', 'atlas_brain_obstacles.json')))
    for f in obst:
        if f['ref'] in keep and f['holes']:
            bh['AM ' + f['ref']] = tuple(f['holes'][0]['c'])
    over = []
    for r, (x, y) in sorted(bh.items()):
        dx = x - stack.BRAIN_DX
        best = min(dh.items(), key=lambda kv: math.hypot(kv[1][0] - dx, kv[1][1] - y))
        dist = math.hypot(best[1][0] - dx, best[1][1] - y)
        over.append((r, best[0], round(dist, 3)))
        if dist > HOLE_TOL:
            bad.append(f'brain hole {r} at drive ({dx:.2f}, {y:.2f}) has no drive hole under it '
                       f'(nearest {best[0]}, {dist:.2f} mm)')
    for line in bad:
        print('PROBLEM', line)
    print(f'stack check: 40 pins x 2 boards, {len(bh)} brain holes {over}, gap {stack.STACK_GAP} mm; '
          f'{len(bad)} problems')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
