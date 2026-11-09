# COOM conformance suite

Each folder holds models (`*.model`) and session tests (`*.test`) written in the COOM
test syntax. An implementation conforms to a profile when it passes every test of that folder.

| folder | profile or module |
|---|---|
| `CORE` | required core |
| `N-OUT`, `N-LIN`, `N-FULL` | numerical calculations |
| `C-FIX`, `C-USER`, `C-OPEN` | cardinalities and instances |
| `D-BASE`, `D-COND` | defaults |
| `O` | optimization |
| `UI` | hide and readonly |
| `TEST` | the test syntax itself |
| `syntax` | parse-only positives and negatives |
| `compile-errors` | models with expected diagnostics |
| `results` | published results per implementation and version |

## State

The folders hold the profile example models from https://www.coom-lang.org. Session tests, the syntax corpus and the
compile error catalogue follow.
