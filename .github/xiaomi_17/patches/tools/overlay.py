#!/usr/bin/env python3
"""Apply per-kernel overlays to the upstream SUSFS kernel patch.

An overlay replaces the upstream per-file diff on kernels where its hooks do not apply.
It records the sha256 of the upstream diff it was adapted from, and apply fails if that
diff has changed.

apply        rewrite the patch in place (exit 0 applied, 2 no overlay, 1 error)
verify-tree  structure checks on the patched tree
make         derive an overlay from the upstream and adapted patches
check        recompose the adapted patches from the baseline and compare hashes
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OVERLAYS = ROOT / "overlays"


def read_lf(path):
    return pathlib.Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_patch(text):
    parts = re.split(r"(?m)^(?=diff --git )", text)
    pre = "" if parts[0].startswith("diff --git") else parts[0]
    blocks = [
        (re.match(r"diff --git a/(\S+) b/", p).group(1), p)
        for p in parts
        if p.startswith("diff --git")
    ]
    return pre, blocks


def overlay_name(fname):
    return fname.replace("/", "__") + ".patch"


def overlay_dir(version, sublevel, os_patch_level):
    kernel = version.split("-", 1)[1]
    return OVERLAYS / version / f"{kernel}.{sublevel}-{os_patch_level}"


def compose(upstream_text, odir):
    """Return (patch_text, manifest).  Raises SystemExit on any guard failure."""
    manifest = json.loads((odir / "manifest.json").read_text(encoding="utf-8"))
    pre, blocks = split_patch(upstream_text)
    by_file = {f: i for i, (f, _) in enumerate(blocks)}
    for fname, expected in manifest["files"].items():
        if fname not in by_file:
            sys.exit(
                f"overlay guard: upstream SUSFS patch no longer touches {fname}; review {odir.name}"
            )
        current = sha(blocks[by_file[fname]][1])
        if current != expected:
            sys.exit(
                f"overlay guard: upstream SUSFS hooks for {fname} changed (sha256 {current[:12]} != "
                f"validated {expected[:12]}).\nReview and regenerate the overlay in {odir} "
                f"before using this SUSFS pin on this kernel."
            )
        blocks[by_file[fname]] = (fname, read_lf(odir / overlay_name(fname)))
    return pre + "".join(b for _, b in blocks), manifest


def cmd_apply(a):
    odir = overlay_dir(a.version, a.sublevel, a.os_patch_level)
    if not (odir / "manifest.json").exists():
        print(f"overlay: none for {odir.name}; upstream patch used unchanged")
        return 2
    path = pathlib.Path(a.patch_file)
    text, manifest = compose(read_lf(path), odir)
    path.write_bytes(text.encode("utf-8"))
    print(f"overlay: applied {odir.name} ({', '.join(manifest['files'])})")
    return 0


def function_body(src, signature):
    m = re.search(re.escape(signature) + r".*?\n}\n", src, re.S)
    return m.group(0) if m else ""


def cmd_verify_tree(a):
    odir = overlay_dir(a.version, a.sublevel, a.os_patch_level)
    if not (odir / "manifest.json").exists():
        return 2
    manifest = json.loads((odir / "manifest.json").read_text(encoding="utf-8"))
    if "fs/proc/task_mmu.c" not in manifest["files"]:
        return 0
    src = read_lf(pathlib.Path(a.kernel_dir) / "fs/proc/task_mmu.c")
    guard = "SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file))"
    roll = function_body(src, "static int show_smaps_rollup(")
    smap = function_body(src, "static int show_smap(")
    problems = []
    if roll.count(guard) != 3:
        problems.append(f"show_smaps_rollup guards={roll.count(guard)} (want 3)")
    if smap.count(guard) != 1:
        problems.append(f"show_smap guards={smap.count(guard)} (want 1)")
    if roll.count("goto bypass_orig_flow") != 1 or roll.count("bypass_orig_flow:") != 1:
        problems.append("show_smaps_rollup bypass_orig_flow goto/label count != 1/1")
    lines = roll.split("\n")
    for i, line in enumerate(lines):
        if "smap_gather_stats(" in line:
            before = "\n".join(lines[max(0, i - 5) : i])
            if guard not in before and "#else" not in "\n".join(
                lines[max(0, i - 2) : i]
            ):
                problems.append(
                    f"unguarded smap_gather_stats in show_smaps_rollup: {line.strip()}"
                )
    if problems:
        print("verify-tree FAILED:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    print(f"verify-tree: {odir.name} task_mmu.c structure OK")
    return 0


def cmd_make(a):
    _, up = split_patch(read_lf(a.upstream))
    adapted_text = read_lf(a.adapted)
    _, ad = split_patch(adapted_text)
    up_d, ad_d = dict(up), dict(ad)
    if list(up_d) != list(ad_d):
        sys.exit("file lists differ between upstream and adapted patch")
    odir = pathlib.Path(a.out)
    odir.mkdir(parents=True, exist_ok=True)
    files = {}
    for fname in up_d:
        if up_d[fname] != ad_d[fname]:
            (odir / overlay_name(fname)).write_bytes(ad_d[fname].encode("utf-8"))
            files[fname] = sha(up_d[fname])
    manifest = {
        "baseline": a.baseline,
        "susfs_commit": a.commit,
        "files": files,
        "composed_sha256": sha(adapted_text),
    }
    (odir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{odir.name}: overlay files {list(files)}")
    return 0


def cmd_check(_):
    bad = 0
    for mf in sorted(OVERLAYS.rglob("manifest.json")):
        manifest = json.loads(mf.read_text(encoding="utf-8"))
        text, _m = compose(read_lf(ROOT / manifest["baseline"]), mf.parent)
        ok = sha(text) == manifest["composed_sha256"]
        print(f"{mf.parent.name}: {'OK' if ok else 'MISMATCH'}")
        bad += not ok
    return 1 if bad else 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("apply", "verify-tree"):
        s = sub.add_parser(name)
        s.add_argument("--version", required=True)
        s.add_argument("--sublevel", required=True)
        s.add_argument("--os-patch-level", required=True)
        s.add_argument(
            "--patch-file" if name == "apply" else "--kernel-dir", required=True
        )
    s = sub.add_parser("make")
    for arg in ("--upstream", "--adapted", "--out", "--baseline", "--commit"):
        s.add_argument(arg, required=True)
    sub.add_parser("check")
    a = p.parse_args()
    sys.exit(
        {
            "apply": cmd_apply,
            "verify-tree": cmd_verify_tree,
            "make": cmd_make,
            "check": cmd_check,
        }[a.cmd](a)
    )


if __name__ == "__main__":
    main()
