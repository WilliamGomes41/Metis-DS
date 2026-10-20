# D5 bounded evidence classification

The existing `LAWS.bend` files remain unchanged. This isolated model checks that
retained native JUnit observations satisfy the D5 evidence condition: both
Python versions, both console classes, all fifteen phases, and zero mirror
accesses in control, guarded and poisoned runs. Xfail and skip cannot be PASS.
It proves the classification of supplied observations, not Python correctness,
guard completeness, recovery, rollback, or a merge/deployment decision.

Capture the executed native reports and check the laws:

```sh
bend guide
python experiments/bend/pr-d5/check.py --junit 3.12=/path/312.xml --junit 3.13=/path/313.xml
```

Later, `python experiments/bend/pr-d5/check.py` rechecks the retained evidence.
The checker creates `Facts.bend` in a temporary directory and runs
`bend PROOF.bend` there. Its negative control claims that one mirror access is
clean; Bend must reject that Boolean equality. No repository law is weakened.
The standard checker is not an independent-kernel proof.
