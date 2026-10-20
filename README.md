# Sprout

A tiny garden-themed language and compiler written in Python.
Pipeline: **lexer -> parser -> semantic analysis -> three-address code (TAC)**, plus a small TAC interpreter.

## Usage

    python sprout.py                      # run the built-in demo
    python sprout.py examples/factorial.spr

The compiler prints the TAC, then runs it.

## Language

    plant n: int = 5;          # declare (types: int, bool)
    n = n - 1;                 # assign
    say n;                     # print
    if n > 1 { ... } else { ... }
    grow n > 0 { ... }         # while-style loop
    # comments start with '#'

Operators: `+ - * / %`, `< > <= >= == !=`, `and or not`, unary `-`.

## Grammar

    program  -> stmt*
    stmt     -> 'plant' ID ':' type '=' expr ';'
              | 'say' expr ';'
              | 'if' expr block ('else' block)?
              | 'grow' expr block
              | ID '=' expr ';'
    block    -> '{' stmt* '}'
    type     -> 'int' | 'bool'
    expr     -> or_expr
    or_expr  -> and_expr ('or' and_expr)*
    and_expr -> eq_expr ('and' eq_expr)*
    eq_expr  -> rel_expr (('==' | '!=') rel_expr)*
    rel_expr -> add_expr (('<' | '>' | '<=' | '>=') add_expr)*
    add_expr -> mul_expr (('+' | '-') mul_expr)*
    mul_expr -> unary (('*' | '/' | '%') unary)*
    unary    -> ('not' | '-') unary | primary
    primary  -> NUM | 'true' | 'false' | ID | '(' expr ')'

## Phases

1. **Lexical analysis**: regex-based tokens (keywords, identifiers, numbers, operators, symbols); unknown characters raise a lexical error with line and column.
2. **Syntax analysis**: recursive-descent parser for the grammar above, with line-numbered syntax errors.
3. **Semantic analysis**: scoped symbol table, type checking, undefined-variable and redeclaration errors.
4. **Intermediate code**: three-address code with temporaries (`$t1`, ...) and labels.

## Examples

`examples/` has working programs and one file per error kind (`error_*.spr`).

## Known limitations

- No functions.
- `and` / `or` do not short-circuit.
- `say` on a bool prints `1` or `0`.
- Division and modulo follow Python (floor) semantics.
