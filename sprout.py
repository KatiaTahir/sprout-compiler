
import re, sys, operator

class SproutError(Exception):
    pass

# ---------- Phase 1: Lexer ----------
KEYWORDS = {'plant', 'say', 'if', 'else', 'grow', 'true', 'false',
            'int', 'bool', 'and', 'or', 'not'}
SPEC = [('NUM', r'\d+'), ('ID', r'[A-Za-z_]\w*'),
        ('OP', r'==|!=|<=|>=|[+\-*/%<>=]'), ('SYM', r'[(){};:]'),
        ('SKIP', r'[ \t\r]+|#[^\n]*'), ('NL', r'\n'), ('BAD', r'.')]
MASTER = re.compile('|'.join(f'(?P<{n}>{p})' for n, p in SPEC))

def lex(src):
    toks, line, line_start = [], 1, 0
    for m in MASTER.finditer(src):
        kind, val = m.lastgroup, m.group()
        if kind == 'NL':
            line += 1; line_start = m.end()
        elif kind == 'BAD':
            raise SproutError(f"Lexical error line {line}, col {m.start()-line_start+1}: unexpected '{val}'")
        elif kind != 'SKIP':
            if kind == 'ID' and val in KEYWORDS:
                kind = 'KW'
            toks.append((kind, val, line))
    toks.append(('EOF', '', line))
    return toks

# ---------- Phase 2: Parser (recursive descent -> AST of tuples) ----------
LEVELS = [['or'], ['and'], ['==', '!='], ['<', '>', '<=', '>='], ['+', '-'], ['*', '/', '%']]

class Parser:
    def __init__(self, toks): self.t, self.i = toks, 0
    def peek(self): return self.t[self.i]
    def at(self, v): return self.peek()[1] == v
    def eat(self, val=None, kind=None):
        k, v, l = self.peek()
        if (val and v != val) or (kind and k != kind):
            raise SproutError(f"Syntax error line {l}: expected {val or kind}, found '{v or 'end of file'}'")
        if k != 'EOF': self.i += 1
        return self.t[self.i - 1] if k != 'EOF' else (k, v, l)

    def program(self):
        stmts = []
        while self.peek()[0] != 'EOF': stmts.append(self.stmt())
        return stmts

    def block(self):
        self.eat('{'); body = []
        while not self.at('}'):
            if self.peek()[0] == 'EOF': raise SproutError("Syntax error: missing '}'")
            body.append(self.stmt())
        self.eat('}'); return body

    def stmt(self):
        k, v, l = self.peek()
        if v == 'plant':
            self.eat(); name = self.eat(kind='ID')[1]; self.eat(':')
            ty = self.eat()[1]
            if ty not in ('int', 'bool'): raise SproutError(f"Syntax error line {l}: unknown type '{ty}' (expected int or bool)")
            self.eat('='); e = self.expr(); self.eat(';')
            return ('plant', name, ty, e, l)
        if v == 'say':
            self.eat(); e = self.expr(); self.eat(';'); return ('say', e, l)
        if v == 'if':
            self.eat(); c = self.expr(); then = self.block(); other = None
            if self.at('else'): self.eat(); other = self.block()
            return ('if', c, then, other, l)
        if v == 'grow':
            self.eat(); c = self.expr(); return ('grow', c, self.block(), l)
        if k == 'ID':
            self.eat(); self.eat('='); e = self.expr(); self.eat(';')
            return ('assign', v, e, l)
        raise SproutError(f"Syntax error line {l}: unexpected '{v or 'end of file'}'")

    def expr(self, lvl=0):
        if lvl == len(LEVELS): return self.unary()
        left = self.expr(lvl + 1)
        while self.peek()[1] in LEVELS[lvl] and self.peek()[0] in ('OP', 'KW'):
            _, op, l = self.eat()
            left = ('bin', op, left, self.expr(lvl + 1), l)
        return left

    def unary(self):
        k, v, l = self.peek()
        if v in ('not', '-') and k in ('KW', 'OP'):
            self.eat(); return ('un', v, self.unary(), l)
        return self.primary()

    def primary(self):
        k, v, l = self.peek()
        if k != 'EOF': self.eat()
        if k == 'NUM': return ('num', int(v), l)
        if v in ('true', 'false'): return ('bool', v == 'true', l)
        if k == 'ID': return ('var', v, l)
        if v == '(':
            e = self.expr(); self.eat(')'); return e
        raise SproutError(f"Syntax error line {l}: expected an expression, found '{v or 'end of file'}'")

# ---------- Phase 3: Semantic analysis (scoped symbol table + type checks) ----------
class Semantic:
    def __init__(self): self.scopes = [{}]
    def err(self, l, msg): raise SproutError(f"Semantic error line {l}: {msg}")
    def lookup(self, n):
        for sc in reversed(self.scopes):
            if n in sc: return sc[n]

    def block(self, stmts):
        self.scopes.append({})
        for s in stmts: self.stmt(s)
        self.scopes.pop()

    def stmt(self, n):
        k = n[0]
        if k == 'plant':
            _, name, ty, e, l = n
            if self.lookup(name): self.err(l, f"'{name}' is already planted")
            t = self.expr(e)
            if t != ty: self.err(l, f"cannot store {t} in '{name}' (declared {ty})")
            self.scopes[-1][name] = ty
        elif k == 'assign':
            _, name, e, l = n
            ty = self.lookup(name)
            if not ty: self.err(l, f"'{name}' was never planted")
            t = self.expr(e)
            if t != ty: self.err(l, f"cannot assign {t} to '{name}' (declared {ty})")
        elif k == 'say': self.expr(n[1])
        else:  # if / grow
            c = n[1]
            if self.expr(c) != 'bool': self.err(n[-1], "condition must be bool")
            if k == 'if':
                self.block(n[2])
                if n[3]: self.block(n[3])
            else: self.block(n[2])

    def expr(self, n):
        k = n[0]
        if k == 'num': return 'int'
        if k == 'bool': return 'bool'
        if k == 'var':
            t = self.lookup(n[1])
            if not t: self.err(n[2], f"undefined variable '{n[1]}'")
            return t
        if k == 'un':
            need = 'bool' if n[1] == 'not' else 'int'
            if self.expr(n[2]) != need: self.err(n[3], f"'{n[1]}' needs {need}")
            return need
        _, op, a, b, l = n
        ta, tb = self.expr(a), self.expr(b)
        if op in ('and', 'or'): need, res = 'bool', 'bool'
        elif op in ('==', '!='):
            if ta != tb: self.err(l, f"cannot compare {ta} with {tb}")
            return 'bool'
        elif op in ('<', '>', '<=', '>='): need, res = 'int', 'bool'
        else: need, res = 'int', 'int'
        if ta != need or tb != need: self.err(l, f"'{op}' needs {need} operands, got {ta} and {tb}")
        return res

# ---------- Phase 4: Three-address code ----------
class Gen:
    def __init__(self): self.code, self.nt, self.nl = [], 0, 0
    # '$' can never appear in a user identifier, so temporaries cannot collide with variables
    def tmp(self): self.nt += 1; return f'$t{self.nt}'
    def lab(self): self.nl += 1; return f'L{self.nl}'
    def emit(self, *a): self.code.append(a)

    def block(self, stmts):
        for s in stmts: self.stmt(s)

    def stmt(self, n):
        k = n[0]
        if k in ('plant', 'assign'):
            name, e = (n[1], n[3]) if k == 'plant' else (n[1], n[2])
            self.emit(name, '=', self.expr(e))
        elif k == 'say': self.emit('PRINT', self.expr(n[1]))
        elif k == 'if':
            c = self.expr(n[1]); Lelse, Lend = self.lab(), self.lab()
            self.emit('IFFALSE', c, Lelse); self.block(n[2]); self.emit('GOTO', Lend)
            self.emit(Lelse + ':')
            if n[3]: self.block(n[3])
            self.emit(Lend + ':')
        else:  # grow
            top, end = self.lab(), self.lab()
            self.emit(top + ':'); c = self.expr(n[1])
            self.emit('IFFALSE', c, end); self.block(n[2]); self.emit('GOTO', top); self.emit(end + ':')

    def expr(self, n):
        k = n[0]
        if k == 'num': return str(n[1])
        if k == 'bool': return '1' if n[1] else '0'
        if k == 'var': return n[1]
        if k == 'un':
            o = self.expr(n[2]); t = self.tmp(); self.emit(t, '=', n[1], o)
        else:
            a = self.expr(n[2]); b = self.expr(n[3]); t = self.tmp(); self.emit(t, '=', a, n[1], b)
        return t

# ---------- Bonus: tiny TAC interpreter so programs actually run ----------
BIN = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.floordiv,
       '%': operator.mod, '<': operator.lt, '>': operator.gt, '<=': operator.le,
       '>=': operator.ge, '==': operator.eq, '!=': operator.ne,
       'and': lambda a, b: a and b, 'or': lambda a, b: a or b}

def run(code):
    labels = {c[0][:-1]: i for i, c in enumerate(code) if len(c) == 1}
    env, pc = {}, 0
    val = lambda x: env[x] if x in env else int(x)
    while pc < len(code):
        c = code[pc]; pc += 1
        if len(c) >= 3 and c[1] == '=':
            if len(c) == 3: env[c[0]] = val(c[2])
            elif len(c) == 4: env[c[0]] = int(not val(c[3])) if c[2] == 'not' else -val(c[3])
            else:
                try: env[c[0]] = int(BIN[c[3]](val(c[2]), val(c[4])))
                except ZeroDivisionError: raise SproutError("Runtime error: division by zero")
        elif c[0] == 'PRINT': print(val(c[1]))
        elif c[0] == 'GOTO': pc = labels[c[1]]
        elif c[0] == 'IFFALSE' and not val(c[1]): pc = labels[c[2]]

def compile_source(src):
    ast = Parser(lex(src)).program()
    Semantic().block(ast)
    g = Gen(); g.block(ast)
    return g.code

DEMO = """# factorial of 5, then the sum of even numbers up to 10
plant n: int = 5;
plant f: int = 1;
grow n > 1 {
    f = f * n;
    n = n - 1;
}
say f;

plant i: int = 0;
plant total: int = 0;
grow i < 10 {
    i = i + 1;
    if i % 2 == 0 { total = total + i; }
}
say total;
"""

if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1]) as fh: src = fh.read()
        except OSError as e:
            sys.exit(f"Cannot open '{sys.argv[1]}': {e.strerror}")
    else:
        src = DEMO
    try:
        tac = compile_source(src)
    except SproutError as e:
        sys.exit(str(e))
    print('--- three-address code ---')
    for c in tac: print(c[0] if len(c) == 1 else '    ' + ' '.join(c))
    print('--- output ---')
    try: run(tac)
    except SproutError as e: sys.exit(str(e))
