import os,re,sys,difflib,hashlib
T=os.path.dirname(os.path.abspath(__file__)); CA=os.path.join(T,"..","cache","android16-6.12")
rd=lambda p: open(p,encoding="utf-8",errors="surrogateescape",newline="").read()
exec(open(os.path.join(T,"strip.py"),encoding="utf-8-sig").read())
files=[l.strip() for l in open(os.path.join(CA,"FILES.txt")) if l.strip()]
def encl(lines,i):
    for j in range(i,-1,-1):
        m=re.match(r"[A-Za-z_$].*?\b(\w+)\(",lines[j])
        if m and not re.match(r"\w+:\s*$",lines[j]) and not lines[j].startswith(("#","}")): return m.group(1)
    return ""
allok=True
for b in sorted(d for d in os.listdir(CA) if d.startswith("6.12")):
    v=os.path.join(T,"v_"+b)
    if not os.path.isdir(v): continue
    probs=[]
    # (a) SUSFS compiled out leaves only directive lines
    for f in files:
        n=os.path.join(v,f); a=os.path.join(CA,b,f)
        if not os.path.exists(n): continue
        pr,new=rd(a),rd(n)
        if pr==new: continue
        off=strip(new)
        for l in difflib.unified_diff(pr.split("\n"),off.split("\n"),lineterm="",n=0):
            if l[:1] in "+-" and l[:3] not in ("+++","---") and l[1:].strip() and not re.match(r"[+-]\s*#\s*(if|ifdef|ifndef|else|endif)\b",l) and "susfs.o" not in l: probs.append(("off-config code diff",f,l[:70]))
    # (b) placement of adapted edits
    tm=rd(os.path.join(v,"fs/proc/task_mmu.c")).split("\n")
    guards=[(i,encl(tm,i)) for i,l in enumerate(tm) if "SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file))" in l]
    roll=[g for g in guards if g[1]=="show_smaps_rollup"]; smap=[g for g in guards if g[1]=="show_smap"]
    fn=re.search(r"static int show_smaps_rollup\(.*?\n}\n",rd(os.path.join(v,"fs/proc/task_mmu.c")),re.S).group(0).split("\n")
    unguard=[i for i,l in enumerate(fn) if "smap_gather_stats(" in l and "SUSFS_IS_INODE_SUS_MAP" not in "\n".join(fn[max(0,i-5):i]) and not any("#else" in x for x in fn[max(0,i-2):i])]
    gl=sum("goto bypass_orig_flow" in l for l in fn); lb=sum("bypass_orig_flow:" in l for l in fn)
    if len(roll)!=3 or len(smap)!=1 or unguard or gl!=1 or lb!=1: probs.append(("rollup/smap structure",len(roll),len(smap),unguard,gl,lb))
    for f,sig,exp in (("fs/exec.c","susfs_def.h",None),("fs/proc/base.c","susfs_def.h",None),("security/selinux/hooks.c","my_setprocattr",None)):
        if sig not in rd(os.path.join(v,f)): probs.append(("missing payload",f))
    # (c) upstream-vs-final hunk sanity: patch file stored hash
    h=hashlib.sha256(open(os.path.join(T,"out_"+b+".patch"),"rb").read()).hexdigest()[:12]
    print(f"{b:18} rollup guards={len(roll)} smap guards={len(smap)} problems={probs or 'none'} patch={h}")
    allok&=not probs
print("ALL OK" if allok else "PROBLEMS")

