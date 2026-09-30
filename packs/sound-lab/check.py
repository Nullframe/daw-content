"""Fail unless every built file matches the sha256 daw's sound-lab recipes pin (pins.json)."""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1]
pins = json.load(open(os.path.join(HERE, "pins.json")))
bad = []
for f, want in sorted(pins.items()):
    p = os.path.join(out, f)
    got = hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else "missing"
    if got != want:
        bad.append(f"{f}: want {want}, got {got}")
print(f"{len(pins) - len(bad)}/{len(pins)} files match the pins")
if bad:
    print("\n".join(bad))
    sys.exit(1)
