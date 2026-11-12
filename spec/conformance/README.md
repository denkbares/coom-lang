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

## Session tests

A file `Name.test` holds the test blocks for `Name.model` in the same folder. Both files are compiled together as one
model, so the test file contains nothing but `test` blocks and may refer to every type of the model. Further models
next to the profile examples cover behaviour the examples do not show.

Every test block is a session of its own that starts without inputs. Its steps run in order and the test fails with
its first failing step.

| step | passes if |
|---|---|
| `set p = v`, `set p` | the inputs with `p` set have a completion, a path to an instance without value creates it |
| `remove p`, `reset p` | always, the input of `p` is dropped |
| `isAvailable p = v`, `isAvailable p` | the inputs with `p = v`, or the instance `p`, added have a completion |
| `isBlocked p = v`, `isBlocked p` | the inputs with `p = v`, or the instance `p`, added have no completion |
| `isFixed p = v` | `p` holds `v` and the value is selected or held in every completion of the inputs |
| `isShown p = v` | `p` is not hidden and holds `v` as a selection, a consequence or an applied default |
| `isEmpty p` | `p` holds no value or one chosen only to complete the configuration |
| `isHidden p` | the effective directive of `p` is `hide`, inherited from the slots holding its instance |
| `isHidden p = o` | the option `o` of `p` is hidden |
| `isReadonly p` | the effective directive of `p` is `readonly` or `hide` |

`isAvailable` and `isBlocked` never change the inputs and ignore defaults. They accept every value type, the value
may only be left out for a path to a structure feature. `isFixed`, `isShown`, `isEmpty`, `isHidden` and `isReadonly`
read the configuration the inputs are completed to with defaults applied, so the conditions of visibilities are judged
on completed values. `isHidden` and `isReadonly` do not depend on the value of `p` or its role. The value is optional
for `isFixed` and `isShown`.

## State

The folders hold the profile example models from https://www.coom-lang.org and session tests for every profile except `O`. The syntax corpus and the compile error catalogue follow.
