import re
import json
import sys
from typing import List, Dict, Any, Optional, Tuple

# ────────────────────────────────────────────────
#  Helper: extract balanced {} block starting at position
# ────────────────────────────────────────────────
def extract_brace_block(code: str, start: int) -> Tuple[Optional[str], int]:
    if start >= len(code) or code[start] != '{':
        return None, start
    count = 1
    i = start + 1
    while i < len(code) and count > 0:
        if code[i] == '{':
            count += 1
        elif code[i] == '}':
            count -= 1
        i += 1
    if count == 0:
        return code[start + 1:i - 1].strip(), i
    return None, i

# ────────────────────────────────────────────────
#  Parser functions
# ────────────────────────────────────────────────
def parse_includes(code: str) -> List[str]:
    return re.findall(r'include\s+<([^>]+)>', code)

def parse_defines(code: str) -> List[Dict[str, str]]:
    pattern = r'def:(\w+)\s*=\s*([^;]+?)\s*;'
    matches = re.finditer(pattern, code)
    return [{"name": m.group(1), "value": m.group(2).strip()} for m in matches]

def parse_structs(code: str) -> List[Dict]:
    structs = []
    pattern = r'struct:(\w+)\s*=\s*\{(.*?)\}\s*;'
    for m in re.finditer(pattern, code, re.DOTALL | re.MULTILINE):
        name = m.group(1)
        fields_raw = m.group(2).strip()
        fields = []
        for line in fields_raw.split(';'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            t, n = [x.strip() for x in line.split(':', 1)]
            fields.append({"type": t, "name": n})
        structs.append({"name": name, "fields": fields})
    return structs

def parse_top_level(code: str) -> Dict:
    result = {
        "includes": parse_includes(code),
        "defines": parse_defines(code),
        "structs": parse_structs(code),
        "functions": [],
        "globals": []
    }

    # Top-level function / main pattern
    func_pattern = r'(?P<rettype>fn|int|void|char\s*\*|[a-zA-Z_][\w:]*)\s*:\s*(?P<name>\w+)\s*=\s*\(\s*(?P<params>[^)]*?)\s*\)\s*=>\s*\{'
    pos = 0
    while True:
        m = re.search(func_pattern, code[pos:])
        if not m:
            break
        start = pos + m.start()
        rettype = m.group("rettype").strip()
        name = m.group("name")
        params_str = m.group("params").strip()
        brace_pos = start + m.end() - 1   # {
        body, new_pos = extract_brace_block(code, brace_pos)
        if body is None:
            pos = start + m.end()
            continue

        # Parse parameters
        params = []
        if params_str:
            for part in re.split(r'\s*\|\s*', params_str):
                part = part.strip()
                if not part:
                    continue
                if ':' in part:
                    typ, nam = [x.strip() for x in part.split(':', 1)]
                else:
                    typ = ""
                    nam = part
                if nam.startswith('*'):
                    typ += ' *'
                    nam = nam[1:].strip()
                params.append({"type": typ, "name": nam})

        return_type = None if rettype == "fn" else rettype.replace(":", " ")
        result["functions"].append({
            "name": name,
            "return_type": return_type,
            "params": params,
            "body": body
        })

        pos = new_pos

    # Global variables like int:score_multiplier = 100;
    global_pattern = r'(?<!for:)(?<!if:)(?<!match:)(?P<type>int|char|bool|float|double|[a-zA-Z_][\w:]*)\s*:\s*(?P<name>\w+)\s*=\s*(?P<value>[^;]+?)\s*;'
    for m in re.finditer(global_pattern, code):
        result["globals"].append({
            "type": m.group("type").replace(":", " "),
            "name": m.group("name"),
            "value": m.group("value").strip()
        })

    return result

# ────────────────────────────────────────────────
#  Very basic body transpiler (hyp → C)
# ────────────────────────────────────────────────
def transpile_body(body: str) -> str:
    lines = body.splitlines()
    out = []
    indent_level = 0

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        # for:loop = (init | cond | incr) =>
        m_loop = re.match(r'^for:loop\s*=\s*\(\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\)\s*=>\s*(?:\{)?$', stripped)
        if m_loop:
            init, cond, incr = [x.strip() for x in m_loop.groups()]
            init = init.replace(":", " ")
            out.append(" " * (4 * indent_level) + f"for ({init}; {cond}; {incr}) {{")
            indent_level += 1
            i += 1
            continue

        # for:each = (array | elem | [index]) =>
        m_each = re.match(r'^for:each\s*=\s*\(\s*([^|]+?)\s*\|\s*([^|]+?)(?:\s*\|\s*([^|]+?))?\s*\)\s*=>\s*(?:\{)?$', stripped)
        if m_each:
            arr, elem, idx_opt = m_each.groups()
            arr = arr.strip()
            elem = elem.strip()
            idx_name = "i"
            if idx_opt:
                idx_opt = idx_opt.strip()
                if ':' in idx_opt:
                    _, idx_name = [x.strip() for x in idx_opt.split(':', 1)]

            size_var = "MAX_PLAYERS" if "players" in arr else "argc" if "argv" in arr else "/*TODO size*/"
            elem_type, elem_name = elem.split(':', 1) if ':' in elem else ("auto", elem)
            elem_type = elem_type.replace("struct:", "struct ").strip()
            elem_name = elem_name.strip().lstrip('*')
            pointer = "*" if "*" in elem else ""

            out.append(" " * (4 * indent_level) + f"for (int {idx_name} = 0; {idx_name} < {size_var}; {idx_name}++) {{")
            indent_level += 1
            out.append(" " * (4 * indent_level) + f"{elem_type} {pointer}{elem_name} = &{arr}[{idx_name}];")
            i += 1
            continue

        # if:(...) =>
        m_if = re.match(r'^if:\s*\(\s*(.+?)\s*\)\s*=>\s*(?:\{)?$', stripped)
        if m_if:
            cond = m_if.group(1).strip()
            out.append(" " * (4 * indent_level) + f"if ({cond}) {{")
            indent_level += 1
            i += 1
            continue

        # match: (very naive for now)
        if stripped.startswith("match:"):
            out.append(" " * (4 * indent_level) + f"/* match not yet transpiled: {stripped} */")
            i += 1
            continue

        # Normalize type:name = → type name =
        line = re.sub(r'(\w+):(\w+)\s*=', r'\1 \2 =', line)

        # Close block if line is just }
        if stripped == "}":
            indent_level = max(0, indent_level - 1)
            out.append(" " * (4 * indent_level) + "}")
            i += 1
            continue

        # Normal line
        if stripped:
            out.append(" " * (4 * indent_level) + line.strip())

        i += 1

    # Force close remaining blocks (safety)
    while indent_level > 0:
        indent_level -= 1
        out.append(" " * (4 * indent_level) + "}")

    return "\n".join(out)

def transpile_to_c(parsed: Dict) -> str:
    lines = []

    lines.append("// Generated C code from hypothetical language (.xc)")
    lines.append("// ==================================================\n")

    # Includes
    inc_map = {"stdio": "stdio.h", "string": "string.h"}
    for inc in parsed["includes"]:
        real_inc = inc_map.get(inc, inc + ".h")
        lines.append(f"#include <{real_inc}>")
    lines.append("#include <stdbool.h>\n")

    # Defines
    for d in parsed["defines"]:
        lines.append(f"#define {d['name']} {d['value']}")
    lines.append("")

    # Globals
    for g in parsed["globals"]:
        lines.append(f"{g['type']} {g['name']} = {g['value']};")
    lines.append("")

    # Structs
    for s in parsed["structs"]:
        lines.append(f"struct {s['name']} {{")
        for f in s["fields"]:
            t = f["type"].replace(":", " ")
            lines.append(f"    {t} {f['name']};")
        lines.append("};\n")

    # Functions
    for fn in parsed["functions"]:
        ret = fn["return_type"] or "void"
        if fn["name"] == "main":
            ret = "int"

        params_str = ", ".join(
            f"{p['type'].replace(':', ' ')} {p['name']}" for p in fn["params"]
        ) or "void"

        lines.append(f"{ret} {fn['name']}({params_str}) {{")
        body_c = transpile_body(fn["body"])
        lines.append(body_c)
        lines.append("}\n")

    return "\n".join(lines)

# ────────────────────────────────────────────────
#  Main entry point
# ────────────────────────────────────────────────
if __name__ == "__main__":
    SOURCE_FILE = "./main.xc"

    try:
        with open(SOURCE_FILE, "r", encoding="utf-8") as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Error: File '{SOURCE_FILE}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    parsed = parse_top_level(source_code)

    print(json.dumps(parsed, indent=2))
    print("\n" + "═" * 70)
    print("TRANSPILED C CODE")
    print("═" * 70)
    print(transpile_to_c(parsed))

    # Quick summary
    print("\nSummary:")
    print(f"  Includes  : {len(parsed['includes'])}")
    print(f"  Defines   : {len(parsed['defines'])}")
    print(f"  Structs   : {len(parsed['structs'])}")
    print(f"  Globals   : {len(parsed['globals'])}")
    print(f"  Functions : {len(parsed['functions'])}")