def strip(src):
    out=[];st=[]
    for ln in src.split("\n"):
        s=ln.strip()
        if re.match(r"#\s*(ifdef|if|ifndef)\b",s):
            sus="CONFIG_KSU_SUSFS" in s; st.append([sus,True,s.startswith("#ifndef")])
            if not sus: out.append(ln)
            continue
        if re.match(r"#\s*else\b",s):
            if st[-1][0]: st[-1][1]=False
            else: out.append(ln)
            continue
        if re.match(r"#\s*endif\b",s):
            e=st.pop()
            if not e[0]: out.append(ln)
            continue
        if all((inif==neg) for sus,inif,neg in st if sus): out.append(ln)
    assert not st; return "\n".join(out)
