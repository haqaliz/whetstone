"""The corpus layer: how a set of tasks is found on disk, above the task contract itself.

`whetstone.verify` owns what a task *is* and what a patch *earns*. This package owns the layer
above that — where manifests live, how a directory of them is read, and (in later slices) how
they are minted. It composes the verifier's loader and adds nothing to the contract.

The split is not organisational tidiness. `whetstone.verify.task` is the provenance boundary,
and `tests/test_task_contract.py` polices it by census: exactly one public callable in that
module may return a `Task`. Anything that reads more than one manifest therefore lives here —
see `whetstone.tasks.manifest` for why that is a real guarantee rather than a relocation.
"""
