from pathlib import Path

# night.py: thread the repair budget through run, freeze, sample and the published contract.
p = Path("src/whetstone/loop/night.py")
t = p.read_text()
old = """    probe: int | None = None,
    retries: bool = True,
    engine: Engine | None = None,"""
new = """    probe: int | None = None,
    retries: bool = True,
    repair: int = 0,
    engine: Engine | None = None,"""
assert old in t
t = t.replace(old, new, 1)
old = "    contract = freeze((*private_tasks, *public_tasks), pool=pool, retry=retries)"
new = (
    "    contract = freeze(\n"
    "        (*private_tasks, *public_tasks), pool=pool, retry=retries, repair=repair > 0\n"
    "    )"
)
assert old in t
t = t.replace(old, new, 1)
old = """        seeder=chosen_seeder,
        retries=retries,
    )"""
new = """        seeder=chosen_seeder,
        retries=retries,
        repair=repair,
    )"""
assert old in t
t = t.replace(old, new, 1)
old = """            declared=declared,
            retries=retries,
            backend_name=runtime.name,
        ),"""
new = """            declared=declared,
            retries=retries,
            repair=repair,
            backend_name=runtime.name,
        ),"""
assert old in t
t = t.replace(old, new, 1)
old = """    declared: Sequence[str],
    retries: bool,
    backend_name: str,
) -> GenerationContract:"""
new = """    declared: Sequence[str],
    retries: bool,
    repair: int,
    backend_name: str,
) -> GenerationContract:"""
assert old in t
t = t.replace(old, new, 1)
old = """        retry_template_sha256=retry_template_sha256() if retries else "",
        diagnosis_vocabulary_version=diagnosis_vocabulary_sha256() if retries else "",
        retrieval="oracle",
    )"""
new = """        retry_template_sha256=retry_template_sha256() if retries else "",
        diagnosis_vocabulary_version=diagnosis_vocabulary_sha256() if retries else "",
        retrieval="oracle",
        repair_budget=repair,
        repair_template_sha256=repair_template_sha256() if repair else "",
    )"""
assert old in t
t = t.replace(old, new, 1)
old = "from whetstone.bakeoff.retry import RETRY_BUDGET"
if old in t:
    t = t.replace(old, old + ", repair_template_sha256", 1)
else:
    raise SystemExit("RETRY_BUDGET import not found")
p.write_text(t)
print("night patched")

# report.py: the published contract gains the repair fields, defaulted for old sidecars.
p = Path("src/whetstone/bakeoff/report.py")
t = p.read_text()
old = """    #: The retrieval setting the prompts were rendered under. `"oracle"` today (the disclosed
    #: setting of `_ORACLE_DISCLOSURE`); a field rather than a constant so two contracts can
    #: be told apart programmatically (`p2-yield-probe/prd.md` D9), which § 10.1 asks for.
    retrieval: str
"""
new = """    #: The retrieval setting the prompts were rendered under. `"oracle"` today (the disclosed
    #: setting of `_ORACLE_DISCLOSURE`); a field rather than a constant so two contracts can
    #: be told apart programmatically (`p2-yield-probe/prd.md` D9), which § 10.1 asks for.
    retrieval: str

    #: How many repair draws a (candidate, task) may get after a NOT_SOLVED verdict. `0` is the
    #: no-repairs state: a contract without repair prompts frozen into it declares no budget.
    repair_budget: int = 0

    #: A digest of the repair instruction, recomputable with stdlib alone. Blank exactly when
    #: `repair_budget` is `0`.
    repair_template_sha256: str = ""
"""
assert old in t
t = t.replace(old, new, 1)
old = """            retrieval=block.get("retrieval", "oracle"),
        )"""
new = """            retrieval=block.get("retrieval", "oracle"),
            repair_budget=block.get("repair_budget", 0),
            repair_template_sha256=block.get("repair_template_sha256", ""),
        )"""
assert old in t
t = t.replace(old, new, 1)
p.write_text(t)
print("report patched")

# cli.py: --repair on the run door.
p = Path("src/whetstone/cli.py")
t = p.read_text()
old = """            retries=not args.no_retries,
            prefer=args.runtime,"""
new = """            retries=not args.no_retries,
            repair=args.repair,
            prefer=args.runtime,"""
assert old in t
t = t.replace(old, new, 1)
# the parser option, beside --no-retries
marker = '    run_parser.add_argument(\n        "--no-retries",'
if marker in t:
    i = t.index(marker)
    insert = '''    run_parser.add_argument(
        "--repair",
        type=int,
        default=0,
        metavar="N",
        help=(
            "re-ask up to N times with the pre-posed repair prompt after a patch applies and "
            "the tests fail (0 disables; the repair prompts are frozen into the contract)"
        ),
    )
'''
    t = t[:i] + insert + t[i:]
else:
    raise SystemExit("--no-retries block not found")
p.write_text(t)
print("cli patched")
