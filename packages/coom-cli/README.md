# coom-cli

The `coom` command for models of the [COOM](https://www.coom-lang.org) product configuration language.

```
pip install coom-cli
coom lint
```

A model is the set of `*.model` and `*.test` files of the current folder. `-C DIR` runs as if started in another
folder and `-m FILE...` names the files directly. `coom` without arguments prints an overview of all commands with
one example each, `coom help COMMAND` the options of a command and `coom help --all` the complete reference.

| Command | Purpose |
|---|---|
| `lint` | Compile the model and report its diagnostics, `--snippet TEXT` compiles a fragment against it |
| `test` | Run the test blocks of the model |
| `show` | Select items of the model and render them |
| `diff` | Report the semantic difference of two models |
| `solve` | Complete a configuration |
| `explain` | Explain why a value is excluded |
| `edit rename`, `edit remove` | Rename or remove an item together with its references |
| `config apply`, `config show`, `config check` | Apply steps to configurations, evaluate and check them |

So far only `lint` is implemented, the other commands exit with status 2.

Diagnostics go to stderr as `file:line:col: severity code: message`, where the code names the family of the message
(`syntax`, `name`, `type`, `structure`). `--format json` prints a versioned JSON envelope on stdout instead. The exit
status is 0 on success, 1 for a negative answer such as errors in the model and 2 when no answer is possible, for
example after a usage error.

Sources live in the [coom-api repository](https://github.com/denkbares/coom-api) under `packages/coom-cli`.
