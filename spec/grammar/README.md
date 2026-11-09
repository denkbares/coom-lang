# COOM grammar

ANTLR 4 grammar of the COOM language, version 1.0. ANTLR tool and runtime version 4.13.2.

The grammar defines the language itself. Vendor extensions are not part of this repository. An implementation that
extends the language does so in a grammar of its own that imports `COOM.g4` and overrides the rules it widens.

## Files

| file | content |
|---|---|
| `Tokens.g4` | lexer rules: function names, reserved words, names, numbers, comments, line breaks |
| `Base.g4` | names, constants, paths, statement ends, comparison operators |
| `Formula.g4` | arithmetic and functions |
| `Condition.g4` | boolean conditions |
| `Structure.g4` | product, structure, enumeration, attribute, feature, cardinality |
| `Behavior.g4` | behavior blocks and their statements |
| `Testing.g4` | test blocks |
| `Model.g4` | a model file |
| `COOM.g4` | entry grammar, declares the parser base class |

## Names and reserved words

A name is an identifier (a Unicode letter, `_` or `$`, followed by letters, digits, marks and connectors) or a quoted
string. Keywords of the language and the words listed in the `RESERVED` lexer rule cannot be used as identifiers.
Quoting makes any text a name, `"static"` for example. Function names such as `min` and `count` remain usable as
identifiers.

## Statement termination

A statement ends with `;` or with a line break. Line breaks are hidden tokens; the parser decides with the semantic
predicate `newlineBefore()`, which every target implements in a small parser base class named `COOMParserBase`. The
predicate returns true when a line break token precedes the current token with no default channel token in between.

Java:

```java
protected boolean newlineBefore() {
    TokenStream input = getTokenStream();
    for (int i = input.LT(1).getTokenIndex() - 1; i >= 0; i--) {
        Token token = input.get(i);
        if (token.getChannel() == Token.DEFAULT_CHANNEL) return false;
        if (token.getType() == COOMLexer.NEWLINE) return true;
    }
    return false;
}
```

## Building

Java: `antlr4 -package <pkg> -visitor -no-listener COOM.g4`.

Python: the predicate must read `self.newlineBefore()` and `not self.newlineBefore()`. `scripts/build_grammar.py` at
the repository root performs that substitution and writes `src/coom/_parser`.

## Checking

Both targets generate without warnings. The models under `../conformance` parse, and every snippet under
`../conformance/syntax/invalid` is rejected.
