import sys
import re


def transpile_line(line: str) -> str:
    """
    Transpiles one line of weird pseudo-C to more standard C-like syntax.
    Handles function headers, variable declarations, for-loops, returns, and now structs.
    """
    original = line.rstrip()
    stripped = original.strip()

    if not stripped:
        return original

    # ── 1. Struct definition ─────────────────────────────────────
    struct_pattern = r'^struct\s*:\s*(\w+)\s*=\s*\{\s*$'
    m = re.match(struct_pattern, stripped)
    if m:
        struct_name = m.group(1)
        return f"struct {struct_name} {{"

    # ── 2. Struct member (inside struct block) ───────────────────
    member_pattern = r'^(\w+(?:\s*\[\d+\])?)\s*:\s*(\w+)\s*;\s*$'
    m = re.match(member_pattern, stripped)
    if m:
        typ, field_name = m.groups()
        # Handle array like char[50] → char name[50];
        if '[' in typ and ']' in typ:
            base_typ, array_part = typ.split('[', 1)
            return f"    {base_typ.strip()} {field_name}[{array_part}"
        else:
            return f"    {typ} {field_name};"

    # ── 3. Function header ───────────────────────────────────────
    header_pattern = r'^([\w\s*]+?)\s*:\s*(\w+)\s*=\s*\(\s*([^)]*?)\s*\)\s*=>\s*\{'
    m = re.match(header_pattern, stripped)
    if m:
        ret_type, func_name, params_part = m.groups()
        ret_type = ' '.join(ret_type.split())

        param_pairs = [p.strip() for p in params_part.split('|') if p.strip()]
        cleaned_params = []

        for pair in param_pairs:
            if ':' not in pair:
                cleaned_params.append(pair)
                continue
            typ, name = [x.strip() for x in pair.split(':', 1)]
            if name.startswith('*'):
                name = '*' + name[1:].lstrip()
            elif name.endswith('[]'):
                name = name[:-2].strip() + '[]'
            cleaned_params.append(f"{typ} {name}")

        params_str = ", ".join(cleaned_params) if cleaned_params else ""
        # Preserve any trailing content after the {
        rest = original[len(m.group(0)):]
        return f"{ret_type} {func_name}({params_str}) {{" + rest

    # ── 4. Special return ────────────────────────────────────────
    if stripped.startswith("return:") and stripped.endswith(";"):
        expr = stripped[7:-1].strip()
        return "    return " + expr + ";"

    # ── 5. Variable declaration & assignment ─────────────────────
    var_pattern = r'^(\w+)\s*:\s*(\w+)\s*=\s*(.+?);$'
    m = re.match(var_pattern, stripped)
    if m:
        typ, var_name, value = m.groups()
        value = value.strip()
        # Add spaces around operators
        value = re.sub(r'([+\-*/%]=?|[=!<>]=?)', r' \1 ', value)
        value = re.sub(r'\s+', ' ', value).strip()
        return f"    {typ} {var_name} = {value};"

    # ── 6. loop:for pseudo-for ───────────────────────────────────
    for_pattern = r'^loop:for:\(\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^)]+)\s*\)\s*=>\s*\{'
    m = re.match(for_pattern, stripped)
    if m:
        init_part, cond_part, incr_part = [x.strip() for x in m.groups()]

        # Normalize init: int:zx=24 → int zx = 24
        if ':' in init_part and '=' in init_part:
            left, val = init_part.split('=', 1)
            if ':' in left:
                typ, name = [x.strip() for x in left.split(':', 1)]
                init_clean = f"{typ} {name} = {val.strip()}"
            else:
                init_clean = init_part
        else:
            init_clean = init_part

        # Preserve any trailing content
        rest = original[len(m.group(0)):]
        return f"    for ({init_clean}; {cond_part}; {incr_part}) {{" + rest

    # ── 7. Closing brace (just pass through) ─────────────────────
    if stripped == "}":
        return "}"

    # ── 8. Fallback: keep as is (but try to indent) ──────────────
    return original


def main():
    if len(sys.argv) < 2:
        print(f"Usage:   {sys.argv[0]} <file.xc>")
        print("Example: python3 ec.py main.xc")
        sys.exit(1)

    filename = sys.argv[1]

    print(f"Transpiling file: {filename}")
    print("───────────────────────────────────────────────\n")

    try:
        with open(filename, encoding="utf-8") as f:
            lines = [line.rstrip('\n') for line in f]

        if not lines:
            print("(empty file)")
            return

        print("Transpiled result:\n")

        indent = 0
        errors = 0

        for i, line in enumerate(lines, 1):
            try:
                t = transpile_line(line)
                stripped_t = t.strip()

                # Very simple indent adjustment
                if stripped_t.endswith("}"):
                    indent = max(0, indent - 1)

                print("    " * indent + t)

                if stripped_t.endswith("{"):
                    indent += 1

            except Exception as e:
                errors += 1
                print(f"  Line {i:3d} ERROR: {e}")
                print("    " * indent + line)

        print("\n───────────────────────────────────────────────")
        print(f"Processed {len(lines)} lines. Errors: {errors}")

    except FileNotFoundError:
        print(f"ERROR: File not found → {filename}")
        sys.exit(2)
    except UnicodeDecodeError:
        print(f"ERROR: Not valid UTF-8 → {filename}")
        sys.exit(3)
    except Exception as e:
        print(f"FATAL: {type(e).__name__}: {e}")
        sys.exit(5)


if __name__ == "__main__":
    main()