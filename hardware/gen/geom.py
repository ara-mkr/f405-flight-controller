# -*- coding: utf-8 -*-
"""Footprint geometry shared by the placer and the board emitter.

KiCad's stock footprints carry IPC-7351 *nominal* (density level B) courtyards,
which are drawn for a general-purpose board with room to spare. On a 37 x 37 mm
four-layer flight controller carrying 118 parts they are the binding constraint:
an 0402 whose body is 1.0 x 0.5 mm gets a 1.82 x 0.92 mm courtyard, so two of
them placed courtyard-to-courtyard sit 0.8 mm apart body-to-body - roughly four
times what the assembler actually needs.

This module recomputes each courtyard at IPC-7351 density level C (*least*, the
level intended for high-density portable assemblies) from the real geometry:

    courtyard = max(pad extents + PAD_M, body outline + BODY_M)

Both the placer and mkpcb.py use this one function, so what the solver packs
against and what KiCad's DRC checks are the same rectangle by construction.
Nothing is ever shrunk inside the copper or inside the moulded body.
"""
import os, re

# IPC-7351 density level C. Widening this to 0.25 to open escape channels was
# measured and rejected: it spreads the parts, lengthens every net and cost 25
# routed connections net of what it gained. The one pad it leaves enclosed is
# handled by seeding each net's island on its roomiest pad instead.
PAD_M  = 0.15    # courtyard excess over the pads
BODY_M = 0.10    # keep clear of the moulded body itself

STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
PROJ  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "fc_f405.pretty")

def span(t, st):
    """End index (exclusive) of the balanced s-expression beginning at `st`.

    Balanced brackets, not a regex: a non-greedy match silently truncates
    multi-line fp_poly/fp_arc blocks and under-reports the extent.
    """
    d = 0; k = st; ins = False
    while k < len(t):
        c = t[k]
        if ins:
            if c == '\\': k += 2; continue
            if c == '"': ins = False
        elif c == '"': ins = True
        elif c == '(': d += 1
        elif c == ')':
            d -= 1
            if d == 0: return k + 1
        k += 1
    raise ValueError("unbalanced")

def fp_path(fpid):
    lib, name = fpid.split(":", 1)
    return (os.path.join(PROJ, name + ".kicad_mod") if lib == "fc_f405"
            else os.path.join(STOCK, lib + ".pretty", name + ".kicad_mod"))

_cache = {}

def _blocks(t, pat):
    pos = 0
    rx = re.compile(pat)
    while True:
        m = rx.search(t, pos)
        if not m: return
        end = span(t, m.start())
        yield t[m.start():end]
        pos = end

def extents(fpid):
    """(pad_bbox, body_bbox, stock_courtyard_bbox); each may be None."""
    if fpid in _cache: return _cache[fpid]
    t = open(fp_path(fpid)).read()
    px = py = bx = by = cx = cy = None
    def grow(acc, vals):
        if not vals: return acc
        lo, hi = min(vals), max(vals)
        return (lo, hi) if acc is None else (min(acc[0], lo), max(acc[1], hi))
    for b in _blocks(t, r'\(pad\s+"'):
        at = re.search(r'\(at (-?[\d.]+) (-?[\d.]+)(?: (-?[\d.]+))?\)', b)
        sz = re.search(r'\(size ([\d.]+) ([\d.]+)\)', b)
        if not (at and sz): continue
        x, y = float(at.group(1)), float(at.group(2))
        w, h = float(sz.group(1)), float(sz.group(2))
        a = float(at.group(3) or 0.0) % 180.0
        if abs(a - 90.0) < 1e-6: w, h = h, w
        px = grow(px, [x - w/2, x + w/2]); py = grow(py, [y - h/2, y + h/2])
    for b in _blocks(t, r'\(fp_(?:line|rect|poly|circle|arc)\b'):
        xs = [float(v) for pair in
              re.findall(r'\((?:start|end|center|mid|xy) (-?[\d.]+) (-?[\d.]+)\)', b)
              for v in (pair[0],)]
        ys = [float(pair[1]) for pair in
              re.findall(r'\((?:start|end|center|mid|xy) (-?[\d.]+) (-?[\d.]+)\)', b)]
        if not xs: continue
        if 'CrtYd' in b:  cx = grow(cx, xs); cy = grow(cy, ys)
        elif 'Fab' in b:  bx = grow(bx, xs); by = grow(by, ys)
    r = ((px, py) if px else None, (bx, by) if bx else None, (cx, cy) if cx else None)
    _cache[fpid] = r
    return r

def courtyard(fpid):
    """(w, h, cx, cy) of the density-level-C courtyard, footprint-local mm."""
    pad, body, stock = extents(fpid)
    xs = []; ys = []
    if pad:  xs += [pad[0][0]-PAD_M,  pad[0][1]+PAD_M ]; ys += [pad[1][0]-PAD_M,  pad[1][1]+PAD_M ]
    if body: xs += [body[0][0]-BODY_M, body[0][1]+BODY_M]; ys += [body[1][0]-BODY_M, body[1][1]+BODY_M]
    if not xs:                                   # nothing to measure - keep stock
        if not stock: raise ValueError("no geometry for " + fpid)
        xs = list(stock[0]); ys = list(stock[1])
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if stock:      # never grow beyond what the library already reserved
        x0 = max(x0, stock[0][0]); x1 = min(x1, stock[0][1])
        y0 = max(y0, stock[1][0]); y1 = min(y1, stock[1][1])
    return (x1-x0, y1-y0, (x0+x1)/2, (y0+y1)/2)
