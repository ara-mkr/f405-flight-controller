"""Minimal KiCad .kicad_sym reader: pull a symbol's full s-expression and its pin geometry."""
import os, re

LIBDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"

def _tokenize(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == '"':
            j = i+1; buf=[]
            while j < n:
                if s[j] == '\\': buf.append(s[j+1]); j += 2; continue
                if s[j] == '"': break
                buf.append(s[j]); j += 1
            out.append(('str', ''.join(buf))); i = j+1
        elif c in '()':
            out.append(('p', c)); i += 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and (not s[j].isspace()) and s[j] not in '()"': j += 1
            out.append(('a', s[i:j])); i = j
    return out

def parse(s):
    toks = _tokenize(s); pos = [0]
    def node():
        assert toks[pos[0]] == ('p','('); pos[0] += 1
        lst = []
        while toks[pos[0]] != ('p',')'):
            t = toks[pos[0]]
            if t == ('p','('): lst.append(node())
            else: lst.append(t[1]); pos[0] += 1
        pos[0] += 1
        return lst
    return node()

def find_all(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]

def find(node, name):
    r = find_all(node, name)
    return r[0] if r else None

_cache = {}
def _lib(libname):
    if libname in _cache: return _cache[libname]
    path = os.path.join(LIBDIR, libname + ".kicad_sym")
    with open(path) as f: txt = f.read()
    _cache[libname] = txt
    return txt

def raw_symbol(libname, symname):
    """Return the exact text of (symbol "symname" ...) including nested children."""
    txt = _lib(libname)
    marker = '(symbol "%s"' % symname
    i = txt.find(marker)
    if i < 0: raise KeyError("%s:%s not found" % (libname, symname))
    depth, j, instr = 0, i, False
    while j < len(txt):
        c = txt[j]
        if instr:
            if c == '\\': j += 2; continue
            if c == '"': instr = False
        elif c == '"': instr = True
        elif c == '(': depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0: return txt[i:j+1]
        j += 1
    raise ValueError("unbalanced")

def pins(libname, symname):
    """{pin_number: (x, y, angle, name, etype)} in symbol-local mm, y already KiCad-sym sign."""
    node = parse(raw_symbol(libname, symname))
    out = {}
    def walk(n):
        for c in n:
            if isinstance(c, list):
                if c and c[0] == 'pin':
                    etype = c[1]
                    at = find(c, 'at'); nm = find(c, 'name'); num = find(c, 'number')
                    ln = find(c, 'length')
                    x, y = float(at[1]), float(at[2])
                    ang = float(at[3]) if len(at) > 3 else 0.0
                    out[num[1]] = dict(x=x, y=y, angle=ang, length=float(ln[1]) if ln else 2.54,
                                       name=nm[1], etype=etype)
                else:
                    walk(c)
    walk(node)
    return out

if __name__ == "__main__":
    import sys, json
    lib, sym = sys.argv[1], sys.argv[2]
    p = pins(lib, sym)
    print(f"{sym}: {len(p)} pins")
    for k in sorted(p, key=lambda s:(len(s),s)):
        v=p[k]; print(f"  {k:>4} {v['name']:<22} at({v['x']:7.2f},{v['y']:7.2f}) ang={v['angle']:5.0f} len={v['length']:.2f} {v['etype']}")
