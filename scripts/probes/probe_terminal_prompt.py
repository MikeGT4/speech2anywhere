import sys
from pathlib import Path
import ollama

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemma3:4b"

PROMPT = (Path(__file__).resolve().parents[2] / "prompts" / "terminal.md").read_text(encoding="utf-8")

TEST_INPUTS = [
    "Okay, dann schauen wir uns morgen früh zuerst die Liste an",
    "Können wir das vielleicht später noch mal in Ruhe besprechen",
    "Hörst du mich?",
    "Okay, wenn das so einfach ist, warum probieren wir es nicht gleich",
    "get status",
    "ssh root att 192 0 2 10",
]

print(f"Testing terminal.md gegen {MODEL} auf {len(TEST_INPUTS)} Inputs\n")
print("=" * 70)

bad_outputs = 0
for inp in TEST_INPUTS:
    prompt = PROMPT.format(text=inp)
    try:
        resp = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2},
            keep_alive="5m",
            **({"think": False} if "qwen3" in MODEL.lower() else {}),
        )
        out = resp["message"]["content"].strip()
        is_bug = (
            out.lower() == "git status"
            and "get status" not in inp.lower()
            and "git status" not in inp.lower()
        )
        if is_bug:
            bad_outputs += 1
            tag = "BUG"
        else:
            tag = "OK "
        print(f"\n[{tag}] IN  ({len(inp):3d}c): {inp[:60]!r}")
        print(f"      OUT ({len(out):3d}c): {out[:80]!r}")
    except Exception as e:
        print(f"\n[ERR] IN: {inp[:60]!r}\n      {e}")

print("\n" + "=" * 70)
print(f"Buggy outputs: {bad_outputs} / {len(TEST_INPUTS)}")
