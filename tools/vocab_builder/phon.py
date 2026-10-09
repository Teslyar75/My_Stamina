"""Own code: ARPAbet (CMUdict) -> IPA, respelling, syllables, guide/notes (Russian)."""
import re
V = {"AA":"ɑ","AE":"æ","AH":"ʌ","AO":"ɔ","AW":"aʊ","AY":"aɪ","EH":"ɛ","ER":"ɝ","EY":"eɪ","IH":"ɪ","IY":"i","OW":"oʊ","OY":"ɔɪ","UH":"ʊ","UW":"u"}
C = {"B":"b","CH":"tʃ","D":"d","DH":"ð","F":"f","G":"ɡ","HH":"h","JH":"dʒ","K":"k","L":"l","M":"m","N":"n","NG":"ŋ","P":"p","R":"r","S":"s","SH":"ʃ","T":"t","TH":"θ","V":"v","W":"w","Y":"j","Z":"z","ZH":"ʒ"}
RV = {"AA":"ah","AE":"a","AH":"uh","AO":"aw","AW":"ow","AY":"eye","EH":"eh","ER":"ur","EY":"ay","IH":"ih","IY":"ee","OW":"oh","OY":"oy","UH":"uu","UW":"oo"}
RC = {"B":"b","CH":"ch","D":"d","DH":"th","F":"f","G":"g","HH":"h","JH":"j","K":"k","L":"l","M":"m","N":"n","NG":"ng","P":"p","R":"r","S":"s","SH":"sh","T":"t","TH":"th","V":"v","W":"w","Y":"y","Z":"z","ZH":"zh"}
ONSETS = {tuple(x.split()) for x in """P T K B D G F V TH DH S Z SH ZH HH CH JH M N L R W Y
P_R P_L T_R K_R K_L K_W B_R B_L D_R G_R G_L F_R F_L TH_R S_P S_T S_K S_M S_N S_L S_W SH_R P_Y B_Y F_Y K_Y M_Y HH_Y V_Y T_W D_W G_W TH_W S_P_R S_T_R S_K_R S_P_L S_K_W S_K_Y""".replace("_"," ").replace("\n"," ").split("  ")} 
ONSETS = set()
for x in "P T K B D G F V TH DH S Z SH ZH HH CH JH M N L R W Y".split(): ONSETS.add((x,))
for x in "P_R P_L T_R K_R K_L K_W B_R B_L D_R G_R G_L F_R F_L TH_R S_P S_T S_K S_M S_N S_L S_W SH_R P_Y B_Y F_Y K_Y M_Y HH_Y V_Y T_W D_W G_W TH_W S_P_R S_T_R S_K_R S_P_L S_K_W S_K_Y".split():
    ONSETS.add(tuple(x.split("_")))

def syllabify(ph):
    """ph: list like ['K','IH1','D'] -> list of syllables [(phones, stress)]"""
    vi = [i for i, p in enumerate(ph) if p[-1].isdigit()]
    if not vi: return [(ph, 0)]
    bounds = [0]
    for a, b in zip(vi, vi[1:]):
        cons = ph[a+1:b]
        k = len(cons)
        # maximal onset
        split = a + 1 + k
        for j in range(0, k + 1):
            on = tuple(cons[j:])
            if not on or on in ONSETS:
                split = a + 1 + j; break
        bounds.append(split)
    bounds.append(len(ph))
    out = []
    for s, e in zip(bounds, bounds[1:]):
        seg = ph[s:e]
        st = next((int(p[-1]) for p in seg if p[-1].isdigit()), 0)
        out.append((seg, st))
    return out

def ipa(ph):
    syl = syllabify(ph)
    parts = []
    for seg, st in syl:
        s = ""
        for p in seg:
            b = p.rstrip("012")
            if b in V:
                v = V[b]
                if b == "AH" and p.endswith("0"): v = "ə"
                if b == "ER" and p.endswith("0"): v = "ɚ"
                if b == "IH" and p.endswith("0") : v = "ɪ"
                s += v
            else: s += C.get(b, b.lower())
        mark = "ˈ" if st == 1 and len(syl) > 1 else ("ˌ" if st == 2 and len(syl) > 1 else "")
        parts.append(mark + s)
    return "/" + "".join(parts) + "/"

def respell(ph):
    syl = syllabify(ph)
    out = []
    for seg, st in syl:
        s = ""
        for p in seg:
            b = p.rstrip("012")
            if b in RV:
                r = RV[b]
                if b == "AH" and p.endswith("0"): r = "uh"
                s += r
            else: s += RC.get(b, b.lower())
        out.append(s.upper() if (st == 1 or len(syl) == 1) else s)
    return "-".join(out)

def stressed_index(ph):
    syl = syllabify(ph)
    for i, (_, st) in enumerate(syl):
        if st == 1: return i
    return 0

ORD = ["1-м", "2-м", "3-м", "4-м", "5-м", "6-м", "7-м", "8-м"]

def guide(word, ph):
    syl = syllabify(ph)
    r = respell(ph)
    if len(syl) == 1:
        return f"Читается как «{r}» — один слог."
    i = stressed_index(ph)
    return f"Читается как «{r}». Ударение на {ORD[min(i,7)]} слоге (выделен заглавными)."

def notes(word, ph):
    w = word.lower(); n = []
    bases = [p.rstrip("012") for p in ph]
    if "TH" in bases: n.append("th глухой [θ]: кончик языка между зубами, без голоса (как в think).")
    if "DH" in bases: n.append("th звонкий [ð]: кончик языка между зубами, с голосом (как в this).")
    if "NG" in bases: n.append("ng [ŋ]: носовой звук задней частью языка (как в sing), не «нг».")
    if "W" in bases: n.append("w: губы округлить, как короткое «у», не «в».")
    if "R" in bases and "ER" not in bases: n.append("r: язык не касается нёба, без раската.")
    if "ER" in bases: n.append("er/ur [ɝ]: не «эр», а один гласный с загнутым языком.")
    if "AE" in bases: n.append("a [æ]: широкий звук между «а» и «э».")
    if "HH" in bases: n.append("h: лёгкий выдох, не «х».")
    if bases and bases[-1] in ("B","D","G","V","Z") : n.append("Звонкий согласный на конце не оглушайте.")
    if re.search(r"^kn|^wr|mb$|^gn|^ps", w): n.append("Есть непроизносимая буква (kn-, wr-, -mb, gn-, ps-).")
    if w.endswith("e") and not w.endswith(("le", "re", "ee", "ye")) and len(w) > 3 and bases and bases[-1].rstrip("012") not in V: n.append("Конечная e не читается.")
    if re.search(r"(tion|sion)$", w): n.append("Окончание -tion/-sion читается [ʃən] — «шн».")
    return n[:4]
