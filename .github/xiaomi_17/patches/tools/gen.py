import os, re, sys, shutil, subprocess, difflib
T=os.path.dirname(os.path.abspath(__file__)); CA=os.path.join(T,"..","cache","android16-6.12")
P=os.environ.get("PATCH_BIN","patch")
rd=lambda p: open(p,encoding="utf-8",errors="surrogateescape",newline="").read()
def wr(p,s):
    os.makedirs(os.path.dirname(p),exist_ok=True); open(p,"w",encoding="utf-8",errors="surrogateescape",newline="").write(s)
G="#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"; GE="#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
def lib():
    L=[]
    # (file, skip-if-present signature, [(anchor, replacement)...] alternatives)
    L.append(("fs/exec.c","susfs_def.h",[
        ("#include <linux/dma-buf.h>\n\n#include <linux/uaccess.h>\n","#include <linux/dma-buf.h>\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs_def.h>\n#endif\n\n#include <linux/uaccess.h>\n"),
        ("#include <linux/ksm.h>\n\n#include <linux/uaccess.h>\n","#include <linux/ksm.h>\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs_def.h>\n#endif\n\n#include <linux/uaccess.h>\n")]))
    L.append(("fs/proc/base.c","CONFIG_KSU_SUSFS_OPEN_REDIRECT)\n#include <linux/susfs_def.h>",[
        ("#include <linux/cpufreq_times.h>\n","#include <linux/cpufreq_times.h>\n#if defined(CONFIG_KSU_SUSFS_SUS_MAP) || defined(CONFIG_KSU_SUSFS_OPEN_REDIRECT)\n#include <linux/susfs_def.h>\n#endif // #if defined(CONFIG_KSU_SUSFS_SUS_MAP) || defined(CONFIG_KSU_SUSFS_OPEN_REDIRECT)\n\n")]))
    L.append(("security/selinux/hooks.c","extern int my_setprocattr",[
        ("struct selinux_state selinux_state;\n","struct selinux_state selinux_state;\n#ifdef CONFIG_KSU_SUSFS\nextern bool ksu_selinux_hide_running __read_mostly;\nextern int my_setprocattr(const char *name, void *value, size_t size);\n#endif // #ifdef CONFIG_KSU_SUSFS\n")]))
    L.append(("fs/proc/task_mmu.c","\t\t\treturn 0;\n\t}\n"+GE,[
        ("static int show_smap(struct seq_file *m, void *v)\n{\n\tstruct vm_area_struct *vma = v;\n\tstruct mem_size_stats mss = {};\n\n",
         "static int show_smap(struct seq_file *m, void *v)\n{\n\tstruct vm_area_struct *vma = v;\n\tstruct mem_size_stats mss = {};\n\n"+G+"\tif (vma->vm_file) {\n\t\tif (SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))\n\t\t\treturn 0;\n\t}\n"+GE+"\n")]))
    return L
ROLL=[ # three edits applied together, only if rollup has no guard yet
 ("\tvma_start = vma->vm_start;\n\tdo {\n\t\tsmap_gather_stats(vma, &mss, 0);\n\t\tlast_vma_end = vma->vm_end;\n",
  "\tvma_start = vma->vm_start;\n\tdo {\n"+G+"\t\tif (vma->vm_file && SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))\n\t\t\tgoto bypass_orig_flow;\n"+GE+"\t\tsmap_gather_stats(vma, &mss, 0);\n"+G+"bypass_orig_flow:\n"+GE+"\t\tlast_vma_end = vma->vm_end;\n"),
 ("\t\t\tif (vma->vm_start >= last_vma_end) {\n\t\t\t\tsmap_gather_stats(vma, &mss, 0);\n\t\t\t\tlast_vma_end = vma->vm_end;\n\t\t\t\tcontinue;\n",
  "\t\t\tif (vma->vm_start >= last_vma_end) {\n"+G+"\t\t\t\tif (!vma->vm_file || !(SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file))))\n\t\t\t\t\tsmap_gather_stats(vma, &mss, 0);\n#else\n\t\t\t\tsmap_gather_stats(vma, &mss, 0);\n"+GE+"\t\t\t\tlast_vma_end = vma->vm_end;\n\t\t\t\tcontinue;\n"),
 ("\t\t\tif (vma->vm_end > last_vma_end) {\n\t\t\t\tsmap_gather_stats(vma, &mss, last_vma_end);\n\t\t\t\tlast_vma_end = vma->vm_end;\n\t\t\t}\n",
  "\t\t\tif (vma->vm_end > last_vma_end) {\n"+G+"\t\t\t\tif (!vma->vm_file || !(SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file))))\n\t\t\t\t\tsmap_gather_stats(vma, &mss, last_vma_end);\n#else\n\t\t\t\tsmap_gather_stats(vma, &mss, last_vma_end);\n"+GE+"\t\t\t\tlast_vma_end = vma->vm_end;\n\t\t\t}\n")]
def run(args,**k): return subprocess.run(args,capture_output=True,text=True,errors="replace",**k)
def apply(pf,w): return run([P,"-p1","-F0","--no-backup-if-mismatch","-d",w,"-i",pf])
def one(b):
    prist=os.path.join(CA,b); k=os.path.join(T,"k_"+b); shutil.rmtree(k,ignore_errors=True); shutil.copytree(prist,k)
    up=rd(os.path.join(T,"up.patch")); r=apply(os.path.join(T,"up.patch"),k)
    rej=sorted(os.path.relpath(os.path.join(dp,f)[:-4],k).replace("\\","/") for dp,_,fs in os.walk(k) for f in fs if f.endswith(".rej"))
    if not rej:
        print(b,"upstream patch already clean - no adaptation"); return True
    # payload of rejected hunks (added lines) for later verification
    payload={}
    for f in rej:
        for hunk in re.findall(r"(?m)^@@.*\n((?:[ +\-\\].*\n?)*)",rd(os.path.join(k,f+".rej"))):
            payload.setdefault(f,[]).append([l[1:] for l in hunk.split("\n") if l.startswith("+") and l[1:].strip()])
    edited=set()
    for f,sig,alts in lib():
        if f not in rej: continue
        cur=rd(os.path.join(k,f))
        if sig in cur: continue
        hit=[(a,n) for a,n in alts if cur.count(a)==1]
        if len(hit)!=1: print(b,"FAIL: no unique anchor for",f,[cur.count(a) for a,_ in alts]); return False
        cur=cur.replace(hit[0][0],hit[0][1]); wr(os.path.join(k,f),cur); edited.add(f)
    tf="fs/proc/task_mmu.c"
    if tf in rej:
        cur=rd(os.path.join(k,tf)); m=re.search(r"static int show_smaps_rollup\(.*?\n}\n",cur,re.S); fn=m.group(0)
        if "bypass_orig_flow" not in fn:
            nf=fn
            for a,n in ROLL:
                if nf.count(a)!=1: print(b,"FAIL: rollup anchor count",nf.count(a),a[:50].replace("\n","|")); return False
                nf=nf.replace(a,n)
            cur=cur.replace(fn,nf); wr(os.path.join(k,tf),cur); edited.add(tf)
    # rebuild patch: replace blocks of edited files with diff of pristine and edited
    for f in sorted(edited):
        pr=rd(os.path.join(prist,f)); cur=rd(os.path.join(k,f))
        dd="".join(difflib.unified_diff(pr.splitlines(True),cur.splitlines(True),"a/"+f,"b/"+f,n=3))
        m=re.search(r"(?m)^diff --git a/"+re.escape(f)+r" b/"+re.escape(f)+r"\n.*?(?=^diff --git |\Z)",up,re.S)
        up=up[:m.start()]+"diff --git a/%s b/%s\n"%(f,f)+dd+up[m.end():]
    out=os.path.join(T,"out_"+b+".patch"); wr(out,up)
    # verify on fresh pristine
    v=os.path.join(T,"v_"+b); shutil.rmtree(v,ignore_errors=True); shutil.copytree(prist,v); r=apply(out,v)
    rj=[f for dp,_,fs in os.walk(v) for f in fs if f.endswith(".rej")]; fz=len(re.findall("fuzz|FAILED",r.stdout))
    miss=[]
    for f,hs in payload.items():
        txt=rd(os.path.join(v,f))
        for h in hs:
            pos=0
            for l in h:
                i=txt.find(l,pos)
                if i<0: miss.append((f,l[:50])); break
                pos=i
    print(b,"edited:",sorted(edited),"| rejects:",len(rj),"| fuzz/failed:",fz,"| rejected-hunk payload missing:",miss or "none")
    return not rj and not fz and not miss
ok=True
for b in sys.argv[1:]: ok=one(b) and ok
sys.exit(0 if ok else 1)
