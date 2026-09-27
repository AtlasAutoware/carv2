"""Read pad rectangles from a TI land-pattern page (vector PDF): python3 pdfpads.py file.pdf page_index mm_per_pt"""
import pymupdf as fitz, sys
def pads(pdf, page, scale_mm_per_pt, color_test=lambda c: c and c[2] > 0.8 and c[0] < 0.3, region=None):
    doc = fitz.open(pdf); pg = doc[page]
    rects = []
    for d in pg.get_drawings():
        if not color_test(d.get('color')): continue
        r = d['rect']
        if region and not (region[0] <= r.x0 <= region[2] and region[1] <= r.y0 <= region[3]): continue
        rects.append([r.x0, r.y0, r.x1, r.y1])
    # cluster touching rects
    groups = []
    for r in rects:
        merged = None
        for g in groups:
            if r[0] <= g[2] + 0.6 and r[2] >= g[0] - 0.6 and r[1] <= g[3] + 0.6 and r[3] >= g[1] - 0.6:
                g[0] = min(g[0], r[0]); g[1] = min(g[1], r[1]); g[2] = max(g[2], r[2]); g[3] = max(g[3], r[3]); merged = g; break
        if not merged: groups.append(list(r))
    # merge groups repeatedly
    changed = True
    while changed:
        changed = False
        out = []
        for g in groups:
            for h in out:
                if g[0] <= h[2] + 0.6 and g[2] >= h[0] - 0.6 and g[1] <= h[3] + 0.6 and g[3] >= h[1] - 0.6:
                    h[0] = min(h[0], g[0]); h[1] = min(h[1], g[1]); h[2] = max(h[2], g[2]); h[3] = max(h[3], g[3]); changed = True; break
            else:
                out.append(list(g))
        groups = out
    return groups
if __name__ == '__main__':
    pdf, page, sc = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
    g = pads(pdf, page, sc)
    xs = [(a[0] + a[2]) / 2 for a in g]; ys = [(a[1] + a[3]) / 2 for a in g]
    print(len(g))
    for a in sorted(g, key=lambda a: (round(a[0]), a[1])):
        print('%7.2f %7.2f  w %5.3f h %5.3f' % ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2, (a[2] - a[0]) * sc, (a[3] - a[1]) * sc))
