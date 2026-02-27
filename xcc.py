#!/usr/bin/env python3
"""
xcc.py
Transpiles .xc (hypothetical language) → C and tries to compile with clang

Usage:
    python3 xcc.py
    # or make it executable: chmod +x xcc.py && ./xcc.py
"""

import re
import subprocess
import sys
import os
from typing import List, Dict, Any, Optional, Tuple

SOURCE_FILE = "./main.xc"
OUTPUT_C_FILE = "./main.c"
OUTPUT_EXEC = "./main"

# ────────────────────────────────────────────────
#  Helper: balanced {} block
# ────────────────────────────────────────────────
def extract_brace_block(code: str, start: int) -> Tuple[Optional[str], int]:
    if start >= len(code) or code[start] != '{':
        return None, start
    count = 1
    i = start + 1
    while i < len(code) and count > 0:
        if code[i] == '{': count += 1
        elif code[i] == '}': count -= 1
        i += 1
    if count == 0:
        return code[start+1:i-1].strip(), i
    return None, i

# ────────────────────────────────────────────────
#  Parser (simplified version tuned for main.xc)
# ────────────────────────────────────────────────
def parse_xc(source: str) -> Dict:
    result = {
        "includes": re.findall(r'include\s+<([^>]+)>', source),
        "defines":  [m.groupdict() for m in re.finditer(r'def:(?P<name>\w+)\s*=\s*(?P<value>[^;]+?)\s*;', source)],
        "structs":  [],
        "globals":  [],
        "functions": []
    }

    # structs
    for m in re.finditer(r'struct:(?P<name>\w+)\s*=\s*\{(?P<body>.*?)\}\s*;', source, re.DOTALL):
        fields = []
        for line in m.group("body").split(';'):
            line = line.strip()
            if not line or ':' not in line: continue
            t, n = [x.strip() for x in line.split(':',1)]
            fields.append({"type": t, "name": n})
        result["structs"].append({"name": m.group("name"), "fields": fields})

    # globals like int:score_multiplier = 100;
    for m in re.finditer(r'(?<!\w:)(?P<type>int|char|bool)\s*:\s*(?P<name>\w+)\s*=\s*(?P<value>[^;]+?)\s*;', source):
        result["globals"].append({
            "type": m.group("type"),
            "name": m.group("name"),
            "value": m.group("value").strip()
        })

    # functions
    func_re = r'(?P<ret>fn|int)\s*:\s*(?P<name>\w+)\s*=\s*\(\s*(?P<params>[^)]*?)\s*\)\s*=>\s*\{'
    pos = 0
    while True:
        m = re.search(func_re, source[pos:])
        if not m: break
        start = pos + m.start()
        ret = m.group("ret")
        name = m.group("name")
        params_str = m.group("params").strip()
        brace_pos = start + m.end() - 1
        body, new_pos = extract_brace_block(source, brace_pos)
        if body is None:
            pos = start + m.end()
            continue

        params = []
        if params_str:
            for p in re.split(r'\s*\|\s*', params_str):
                p = p.strip()
                if not p: continue
                if ':' in p:
                    t, n = [x.strip() for x in p.split(':',1)]
                else:
                    t, n = "", p
                if n.startswith('*'):
                    t += ' *'
                    n = n[1:].strip()
                params.append({"type": t, "name": n})

        return_type = None if ret == "fn" else ret
        result["functions"].append({
            "name": name,
            "return_type": return_type,
            "params": params,
            "body": body
        })
        pos = new_pos

    return result

# ────────────────────────────────────────────────
#  Simple transpiler body → C body
# ────────────────────────────────────────────────
def transpile_body(body: str) -> str:
    lines = body.splitlines()
    out = []
    indent = 0

    for raw_line in lines:
        line = raw_line.strip()
        if not line: continue

        if line.startswith("for:loop = ("):
            # for:loop = (int:i = 0 | i < 10 | i++) =>
            parts = re.match(r'for:loop\s*=\s*\(\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\)\s*=>\s*\{?', line)
            if parts:
                init, cond, step = [p.strip().replace(":"," ") for p in parts.groups()]
                out.append("    " * indent + f"for ({init}; {cond}; {step}) {{")
                indent += 1
                continue

        if line.startswith("for:each = ("):
            # very naive — assumes players or argv
            if "players" in line:
                size = "MAX_PLAYERS"
            elif "argv" in line:
                size = "argc"
            else:
                size = "10 /* todo */"

            m = re.match(r'for:each\s*=\s*\(\s*([^|]+)\s*\|\s*([^|]+)(?:\s*\|\s*([^|]+))?\s*\)\s*=>\s*\{?', line)
            if m:
                coll, elem, idx_opt = m.groups()
                coll = coll.strip()
                elem = elem.strip()
                idx_name = "i"
                if idx_opt:
                    idx_name = idx_opt.split(":")[-1].strip()

                if ":" in elem:
                    et, en = elem.split(":",1)
                    et = et.replace("struct:","struct ").strip()
                    en = en.strip().lstrip("*")
                    star = "*" if "*" in elem else ""
                else:
                    et, en, star = "void*", elem, ""

                out.append("    " * indent + f"for (int {idx_name} = 0; {idx_name} < {size}; {idx_name}++) {{")
                indent += 1
                out.append("    " * indent + f"{et} {star}{en} = &{coll}[{idx_name}];")
                continue

        if line.startswith("if:("):
            cond = line[3:].strip(" )=>{").strip()
            out.append("    " * indent + f"if ({cond}) {{")
            indent += 1
            continue

        if line.startswith("match:("):
            out.append("    " * indent + "/* match → manual if/switch needed */")
            continue

        # normalize type:name =
        line = re.sub(r'(\w+):(\w+)\s*=', r'\1 \2 =', raw_line)

        # closing }
        if line == "}":
            indent = max(0, indent - 1)
            out.append("    " * indent + "}")
            continue

        out.append("    " * indent + line)

    while indent > 0:
        indent -= 1
        out.append("    " * indent + "}")

    return "\n".join(out)

def generate_c_code(parsed: Dict) -> str:
    c = ["// Generated from main.xc using xcc.py (clang frontend)",
         "// ====================================================\n"]

    # includes
    inc_map = {"stdio": "stdio.h", "string": "string.h"}
    for inc in parsed["includes"]:
        c.append(f"#include <{inc_map.get(inc, inc + '.h')}>")
    c.append("#include <stdbool.h>\n")

    # defines
    for d in parsed["defines"]:
        c.append(f"#define {d['name']} {d['value']}")
    c.append("")

    # globals
    for g in parsed["globals"]:
        c.append(f"{g['type']} {g['name']} = {g['value']};")
    c.append("")

    # structs
    for s in parsed["structs"]:
        c.append(f"struct {s['name']} {{")
        for f in s["fields"]:
            t = f["type"].replace(":", " ")
            c.append(f"    {t} {f['name']};")
        c.append("};\n")

    # functions
    for fn in parsed["functions"]:
        ret = fn["return_type"] or "void"
        if fn["name"] == "main":
            ret = "int"

        params = ", ".join(f"{p['type']} {p['name']}" for p in fn["params"]) or "void"
        c.append(f"{ret} {fn['name']}({params}) {{")
        c.append(transpile_body(fn["body"]))
        c.append("}\n")

    return "\n".join(c)

def compile_with_clang():
    if not os.path.isfile(OUTPUT_C_FILE):
        print(f"Error: {OUTPUT_C_FILE} was not generated.")
        return False

    cmd = ["clang", OUTPUT_C_FILE, "-o", OUTPUT_EXEC, "-Wall", "-Wextra", "-std=c11"]
    print(f"Compiling with: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print("Compilation succeeded ✓")
            print(f"Executable created: {OUTPUT_EXEC}")
            if os.access(OUTPUT_EXEC, os.X_OK):
                print("\nYou can now run:")
                print(f"    ./{OUTPUT_EXEC}")
            return True
        else:
            print("Compilation failed:")
            print(result.stderr or "(no error output)")
            return False
    except FileNotFoundError:
        print("Error: clang not found. Please install clang.")
        return False

# ────────────────────────────────────────────────
#  Main
# ────────────────────────────────────────────────
def main():
    if not os.path.isfile(SOURCE_FILE):
        print(f"Error: {SOURCE_FILE} not found.")
        sys.exit(1)

    print(f"Reading {SOURCE_FILE} ...")
    with open(SOURCE_FILE, encoding="utf-8") as f:
        source = f.read()

    print("Parsing ...")
    parsed = parse_xc(source)

    print("Generating C code ...")
    c_code = generate_c_code(parsed)

    print(f"Writing {OUTPUT_C_FILE} ...")
    with open(OUTPUT_C_FILE, "w", encoding="utf-8") as f:
        f.write(c_code)

    print("\n" + "═"*60)
    print("Generated main.c (first 30 lines):")
    print("═"*60)
    print("\n".join(c_code.splitlines()[:30]))
    print("...\n")

    print("Trying to compile with clang ...")
    success = compile_with_clang()

    if success:
        print("\nDone. Try running the program:")
        print(f"    ./{OUTPUT_EXEC}")
    else:
        print("\nFix the code in main.xc or improve the transpiler and try again.")

if __name__ == "__main__":
    main()