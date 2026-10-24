"""Rev B power board (ATLAS-PWR-1) bill of materials and cost, computed from the design so the totals are not typed.

    python3 bom/revb/make_power_bom.py   ->  bom/revb/power_board_bom.csv, bom/revb/power_board_cost.md

Source: boards/power/atlas_power_parts.json (written by boards/tools/build_sch.py power). Each part carries MPN,
Manufacturer, Price (USD at qty 1 on 2026-10-24), Source and Verified (yes = read on the cited page that day,
est. = catalogue estimate, no = not confirmed). Wire pads, mounting holes and bare test pads are not parts.
DNP parts are listed with quantity 0. The PCB itself is priced by agent E (PCBWay quote), not here.
"""
import collections
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PARTS = json.load(open(os.path.join(ROOT, 'boards', 'power', 'atlas_power_parts.json')))['parts']

BLOCKS = {'A_PACK': 'A pack input', 'B_BMS': 'B BMS link', 'C_SWITCH': 'C main switch, precharge, E-stop gate',
          'D_RAILS': 'D latch and rails (5 V, servo, dev kit, lidar, camera)', 'E_CHARGE': 'E USB-C charging',
          'F_DEBUG': 'F debug hub and console', 'G_SUPER': 'G Pico supervisor', 'H_JETSON': 'H Jetson ribbon and J14',
          'I_ESC': 'I ESC interface', 'J_MISC': 'J E-stop, fan, holes'}

# not in the schematic (one set per board): Pico and hub male headers, bolts for the bar, and the DIP sockets that
# go into the U301, U302 and U601 footprints (findchips listing of the Mouser price, read on 2026-10-24)
FC = 'https://www.findchips.com/search/'
EXTRA = [
    ('C_SWITCH', 'DIP-8 socket for U301 MIC5014 (soldered in its footprint)', 'TE 1-2199298-2', 1, 0.27, FC + '1-2199298-2', 'yes'),
    ('C_SWITCH', 'DIP-14 socket for U302 74HCT08 (soldered in its footprint)', 'TE 1-2199298-3', 1, 0.28, FC + '1-2199298-3', 'yes'),
    ('F_DEBUG', 'DIP-14 socket for U601 MCP2221A (soldered in its footprint)', 'TE 1-2199298-3', 1, 0.28, FC + '1-2199298-3', 'yes'),
    ('G_SUPER', 'Male headers for the Pico, 2 x 1x20 (or buy a Pico with headers fitted)', 'generic 1x20 2.54 mm', 2, 0.25, '-', 'est.'),
    ('F_DEBUG', 'Male headers for the hub module, 2 x 1x8 + 1x4 (if the module came without them)', 'generic 2.54 mm', 1, 0.30, '-', 'est.'),
    ('C_SWITCH', 'M3 x 8 screws and nuts for the three FET tabs on the bar (all tabs are BAT+, no insulators needed); Kapton tape for the NTC and the outer face of the bar', 'generic', 1, 1.00, '-', 'est.'),
]


def kind(p):
    fp = p['footprint']
    if fp.startswith(('Resistor_SMD', 'Capacitor_SMD')):
        return 'SMD 1206/1210, bottom'
    if 'WireLand' in fp:
        return 'module off board, wired'
    if p['ref'].startswith('MOD'):
        return 'module on sockets'
    if p['ref'].startswith('HS'):
        return 'mechanical'
    return 'through-hole'


def main():
    lines = collections.OrderedDict()
    for p in PARTS:
        f = p['fields']
        if f.get('in_bom') == 'no':
            continue
        key = (f.get('MPN') or p['value'], p['footprint'])
        e = lines.setdefault(key, dict(mpn=f.get('MPN') or '', mfr=f.get('Manufacturer', ''), value=p['value'],
                                        desc=f.get('Description', ''), fp=p['footprint'].split(':')[1],
                                        kind=kind(p), refs=[], dnp=[], blocks=collections.Counter(),
                                        price=float(f.get('Price') or 0), source=f.get('Source', ''),
                                        verified=f.get('Verified', '')))
        (e['dnp'] if p['dnp'] else e['refs']).append(p['ref'])
        if not p['dnp']:
            e['blocks'][p['block']] += 1
    out = os.path.join(HERE, 'power_board_bom.csv')
    with open(out, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['qty', 'refs', 'value', 'mpn', 'manufacturer', 'footprint', 'assembly', 'unit_usd', 'line_usd',
                    'verified', 'source', 'description', 'dnp_refs'])
        for e in lines.values():
            q = len(e['refs'])
            w.writerow([q, ' '.join(e['refs']), e['value'], e['mpn'], e['mfr'], e['fp'], e['kind'], f"{e['price']:.2f}",
                        f"{q * e['price']:.2f}", e['verified'], e['source'], e['desc'], ' '.join(e['dnp'])])
        for blk, item, pn, q, unit, src, ver in EXTRA:
            sock = pn.startswith('TE ')
            w.writerow([q, '-', item, pn, 'TE Connectivity' if sock else '', '-',
                        'through-hole (socket)' if sock else 'loose', f'{unit:.2f}', f'{q * unit:.2f}', ver, src, item, ''])
    # cost per block and counts
    cost = collections.Counter()
    unver = collections.Counter()
    count = collections.Counter()
    for e in lines.values():
        for blk, n in e['blocks'].items():
            cost[blk] += n * e['price']
            count[e['kind']] += n
            if e['verified'] != 'yes':
                unver[blk] += n * e['price']
    for blk, item, pn, q, unit, src, ver in EXTRA:
        cost[blk] += q * unit
        if ver != 'yes':
            unver[blk] += q * unit
        if pn.startswith('TE '):
            count['through-hole'] += q
    total = sum(cost.values())
    md = ['# ATLAS-PWR-1 rev B: parts cost per board', '',
          'Generated by `bom/revb/make_power_bom.py` from `boards/power/atlas_power_parts.json`. Prices are USD at',
          'quantity 1 on 2026-10-24; buying for three boards at once lowers the chip resistors and capacitors to a',
          'few cents each. The bare PCB is quoted separately (PCBWay, agent E). Cables, the BMS, the Castle BEC and',
          'the pack hardware are car-level items in the main cost table.', '',
          '| Block | Parts cost (USD) | Of which not verified (USD) |', '| --- | ---: | ---: |']
    for blk in BLOCKS:
        md.append(f'| {BLOCKS[blk]} | {cost[blk]:.2f} | {unver[blk]:.2f} |')
    md += [f'| **Total per board** | **{total:.2f}** | **{sum(unver.values()):.2f}** |', '',
           '| Assembly class | Parts |', '| --- | ---: |']
    for k in ('through-hole', 'SMD 1206/1210, bottom', 'module on sockets', 'module off board, wired', 'mechanical'):
        md.append(f'| {k} | {count[k]} |')
    md += ['', f'{len(lines)} BOM lines; DNP parts are listed in the CSV with quantity 0.', '']
    open(os.path.join(HERE, 'power_board_cost.md'), 'w').write('\n'.join(md))
    print(f'{out}: {len(lines)} lines; total ${total:.2f} per board; counts {dict(count)}')
    for blk in BLOCKS:
        print(f'  {blk:9s} {cost[blk]:7.2f}  (unverified {unver[blk]:.2f})')


if __name__ == '__main__':
    main()
