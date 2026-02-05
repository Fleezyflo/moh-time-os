#!/usr/bin/env python3.14
from __future__ import annotations

import dis
import marshal
import pathlib
import types
import re
import sys

METHOD_ATTRS = {"get", "post", "put", "delete", "patch", "options", "head", "websocket"}

def load_code_from_pyc(pyc_path: pathlib.Path) -> types.CodeType:
    b = pyc_path.read_bytes()
    if len(b) < 16:
        raise SystemExit("PYC too small")
    # CPython 3.7+ header is 16 bytes
    co = marshal.loads(b[16:])
    if not isinstance(co, types.CodeType):
        raise SystemExit(f"Top-level marshal object is not code: {type(co)}")
    return co

def is_probably_path(s: str) -> bool:
    return isinstance(s, str) and (s.startswith("/") or s.startswith("http://") or s.startswith("https://"))

def signature_from_code(co: types.CodeType) -> str:
    # Best-effort signature: names only (defaults/annotations not recoverable reliably from code obj alone).
    posonly = co.co_posonlyargcount
    poskw = co.co_argcount
    kwonly = co.co_kwonlyargcount

    names = list(co.co_varnames[: poskw + kwonly])
    posonly_names = names[:posonly]
    poskw_names = names[posonly:poskw]
    kwonly_names = names[poskw:poskw + kwonly]

    parts = []
    parts += posonly_names
    if posonly_names:
        parts.append("/")
    parts += poskw_names
    if kwonly_names:
        parts.append("*")
        parts += kwonly_names

    # If function has *args/**kwargs
    flags = co.co_flags
    CO_VARARGS = 0x04
    CO_VARKEYWORDS = 0x08
    i = poskw + kwonly
    if flags & CO_VARARGS:
        parts.append("*" + co.co_varnames[i])
        i += 1
    if flags & CO_VARKEYWORDS:
        parts.append("**" + co.co_varnames[i])
        i += 1

    return ", ".join(parts) if parts else ""

def walk_code_objects(co: types.CodeType):
    seen = set()
    def rec(c: types.CodeType):
        if id(c) in seen:
            return
        seen.add(id(c))
        yield c
        for k in c.co_consts:
            if isinstance(k, types.CodeType):
                yield from rec(k)
    yield from rec(co)

def extract_routes_from_top_level(co: types.CodeType):
    """
    Extract route decorators by scanning top-level bytecode for patterns like:
      app.<method>(<path>, ...)
      @ decorator application to next defined function
    This is a heuristic but works well for FastAPI-style server modules.
    """
    ins = list(dis.get_instructions(co))
    routes = []  # list of dicts: {func, method, path}
    pending = [] # decorators seen since last function def

    last_loaded_const = None
    last_app = False
    last_method = None
    last_path = None

    last_codeobj_loaded = None

    for i, it in enumerate(ins):
        op = it.opname
        av = it.argval

        if op == "LOAD_CONST":
            last_loaded_const = av
            if isinstance(av, types.CodeType):
                last_codeobj_loaded = av

        # Track "app"
        if op in ("LOAD_NAME", "LOAD_GLOBAL") and av == "app":
            last_app = True
            continue

        # Track "app.<method>"
        if last_app and op == "LOAD_ATTR" and isinstance(av, str) and av in METHOD_ATTRS:
            last_method = av.upper() if av != "websocket" else "WEBSOCKET"
            last_path = None
            continue

        # Track first string const after app.<method>
        if last_method and op == "LOAD_CONST" and isinstance(av, str) and is_probably_path(av):
            last_path = av
            continue

        # When decorator call happens, remember it
        if last_method and op in ("CALL", "CALL_FUNCTION", "CALL_METHOD"):
            if last_path:
                pending.append({"method": last_method, "path": last_path})
            last_app = False
            last_method = None
            last_path = None
            continue

        # When function is created, bind pending decorators to it
        if op == "MAKE_FUNCTION":
            # Next STORE_NAME/STORE_FAST commonly holds the function name at module scope
            func_name = None
            for j in range(i+1, min(i+10, len(ins))):
                if ins[j].opname in ("STORE_NAME", "STORE_GLOBAL"):
                    func_name = ins[j].argval
                    break

            if func_name and pending:
                for d in pending:
                    routes.append({"func": func_name, **d})
                pending = []

    # De-dup
    uniq = []
    seen = set()
    for r in routes:
        key = (r["func"], r["method"], r["path"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq

def build_stub_server(pyc_path: pathlib.Path, out_py: pathlib.Path, out_routes: pathlib.Path):
    top = load_code_from_pyc(pyc_path)

    routes = extract_routes_from_top_level(top)
    out_routes.write_text("\n".join([f'{r["method"]:9s} {r["path"]}  ->  {r["func"]}' for r in routes]) + "\n")

    # Map func name -> code object
    func_code = {}
    for c in walk_code_objects(top):
        func_code[c.co_name] = c

    lines = []
    lines.append('from __future__ import annotations\n')
    lines.append('from fastapi import FastAPI\n')
    lines.append('from fastapi.middleware.cors import CORSMiddleware\n\n')
    lines.append('APP_TITLE = "MOH TIME OS API"\n')
    lines.append('app = FastAPI(title=APP_TITLE)\n\n')
    lines.append('app.add_middleware(\n')
    lines.append('    CORSMiddleware,\n')
    lines.append('    allow_origins=["http://localhost:8420","http://localhost:5173","http://localhost:3000","*"],\n')
    lines.append('    allow_credentials=True,\n')
    lines.append('    allow_methods=["*"],\n')
    lines.append('    allow_headers=["*"],\n')
    lines.append(')\n\n')
    lines.append('@app.get("/health")\n')
    lines.append('async def health():\n')
    lines.append('    return {"ok": True, "service": APP_TITLE}\n\n')

    # Emit stubs for discovered routes
    emitted = set()
    for r in routes:
        fn = r["func"]
        if fn in emitted:
            continue
        emitted.add(fn)

        co = func_code.get(fn)
        is_async = bool(co and (co.co_flags & 0x80))  # CO_COROUTINE
        sig = signature_from_code(co) if co else "*args, **kwargs"

        # Choose decorator form
        if r["method"] == "WEBSOCKET":
            dec = f'@app.websocket("{r["path"]}")'
        else:
            dec = f'@app.{r["method"].lower()}("{r["path"]}")'

        lines.append(dec + "\n")
        lines.append(f'{"async " if is_async else ""}def {fn}({sig}):\n')

        # Put disassembly inside docstring so you can rebuild logic deterministically
        if co:
            buf = []
            buf.append(f'Original: {co.co_filename}:{co.co_firstlineno}\n')
            buf.append(dis.Bytecode(co).dis())
            doc = "\n".join(buf)
            # Keep docstring size reasonable
            doc = doc[:20000]
            lines.append('    """\n')
            for ln in doc.splitlines():
                lines.append("    " + ln + "\n")
            lines.append('    """\n')
        lines.append("    raise NotImplementedError\n\n")

    out_py.write_text("".join(lines))

def main():
    if len(sys.argv) < 3:
        print("Usage: python3.14 recover_server_from_pyc_py314.py /path/to/server.cpython-314.pyc /output/dir", file=sys.stderr)
        raise SystemExit(2)

    pyc = pathlib.Path(sys.argv[1]).expanduser().resolve()
    out_dir = pathlib.Path(sys.argv[2]).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_py = out_dir / "server.recovered.stub.py"
    out_routes = out_dir / "server.routes.txt"

    build_stub_server(pyc, out_py, out_routes)
    print("OK")
    print("Wrote:", out_py)
    print("Wrote:", out_routes)

if __name__ == "__main__":
    main()