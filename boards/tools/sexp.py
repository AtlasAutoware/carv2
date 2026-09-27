"""Minimal KiCad s-expression reader and writer."""
import re

TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse(s):
    st = [[]]
    for m in TOK.finditer(s):
        t = m.group(0)
        if t == '(':
            st.append([])
        elif t == ')':
            x = st.pop()
            st[-1].append(x)
        else:
            st[-1].append(t)
    return st[0]


def dump(x, ind=0):
    if not isinstance(x, list):
        return x
    if all(not isinstance(e, list) for e in x) and len(x) < 14:
        return '(' + ' '.join(x) + ')'
    head = []
    i = 0
    while i < len(x) and not isinstance(x[i], list):
        head.append(x[i])
        i += 1
    s = '(' + ' '.join(head)
    for e in x[i:]:
        s += '\n' + '\t' * (ind + 1) + (dump(e, ind + 1) if isinstance(e, list) else e)
    return s + ')'


def find(x, key):
    return [e for e in x if isinstance(e, list) and e and e[0] == key]


def find1(x, key):
    r = find(x, key)
    return r[0] if r else None


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def uq(s):
    if isinstance(s, str) and len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    return s
