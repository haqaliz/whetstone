"""The reward path. Deliberately exports nothing.

Every module under here is on the path that produces the reward, and the AST guard a later
phase adds is scoped to exactly this package: nothing in here may import an inference
library. Re-exporting a symbol from this ``__init__`` would make the import graph of the
guarded package depend on what a caller happens to touch, so callers import the module they
mean (``whetstone.verify.verdict``) and this file stays a package marker.
"""
