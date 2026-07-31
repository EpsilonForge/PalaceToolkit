import json
nb = json.load(open("/home/loloc/PalaceToolkit/docs/examples/l_antenna.ipynb"))
src = nb["cells"][22]["source"]
print("--- Geometry section ---")
for i in range(12, 35):
    print(str(i) + ": " + src[i].rstrip())
print("--- Tag reference ---")
for i, l in enumerate(src):
    if "top_conductor_ch" in l and "tags" in l:
        print(str(i) + ": " + l.rstrip())
print("--- Pipeline code (first 15 lines) ---")
count = 0
for i, l in enumerate(src):
    if "dimtags_2d" in l or "fragment" in l or "pg_map_ch" in l or "frag_order" in l:
        if count < 15:
            print(str(i) + ": " + l.rstrip()[:80])
            count += 1
print("Total lines: " + str(len(src)))
