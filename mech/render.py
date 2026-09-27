"""Shaded PNG renders of CadQuery solids with matplotlib (no GPU).

    render([(solid, (r, g, b)), ...], 'file.png', views=[(elev, azim), ...])

All faces go into one Poly3DCollection per view so matplotlib depth-sorts them together
(separate collections are drawn in insertion order and paint over each other).
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def _tris(shape, tol=0.25):
    verts, tris = shape.tessellate(tol, 0.3)
    v = np.array([(p.x, p.y, p.z) for p in verts])
    return v, np.array(tris)


def render(parts, path, views=((24, -58),), title=None, size=6.0, zoom=1.35):
    fig = plt.figure(figsize=(size * len(views), size * 0.85), dpi=150)
    light = np.array([0.35, -0.55, 0.75]); light /= np.linalg.norm(light)
    cache = []
    for obj, col in parts:
        shape = obj.val() if hasattr(obj, 'val') else obj
        try:
            v, t = _tris(shape)
        except Exception:
            continue
        if len(t) == 0:
            continue
        cache.append((v, t, np.array(col)))
    V = np.vstack([c[0] for c in cache])
    lo, hi = V.min(0), V.max(0)
    ctr = (lo + hi) / 2; r = (hi - lo).max() / 2
    for i, (el, az) in enumerate(views):
        ax = fig.add_subplot(1, len(views), i + 1, projection='3d')
        allP, allC = [], []
        for v, t, col in cache:
            P = v[t]
            n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
            n /= (np.linalg.norm(n, axis=1, keepdims=True) + 1e-9)
            shade = 0.42 + 0.58 * np.abs(n @ light)
            allP.append(P); allC.append(np.clip(col[None, :] * shade[:, None], 0, 1))
        ax.add_collection3d(Poly3DCollection(np.vstack(allP), facecolors=np.vstack(allC), edgecolors='none'))
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(tuple(hi - lo), zoom=zoom); ax.view_init(elev=el, azim=az); ax.set_axis_off()
    if title:
        fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path
