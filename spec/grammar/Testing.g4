// COOM language 1.0, test blocks: sequences of session steps and assertions on a model.
grammar Testing;
import Base, Formula;

test :
    kw='test' name? '{'
        (define | test_statement)*
    '}' ;

define : 'define' name EQ formula ;

test_statement
    : test_set
    | test_remove
    | test_reset
    | test_fixed
    | test_shown
    | test_empty
    | test_available
    | test_blocked
    | test_hidden
    | test_readonly
    ;

test_set       : kw='set' path (EQ formula_atom)? ;
test_remove    : kw='remove' path ;
test_reset     : kw='reset' path ;
test_fixed     : kw='isFixed' path (EQ formula_atom)? ;
test_shown     : kw='isShown' path (EQ formula_atom)? ;
test_empty     : kw='isEmpty' path ;
test_available : kw='isAvailable' path (EQ formula_atom)? ;
test_blocked   : kw='isBlocked' path (EQ formula_atom)? ;
test_hidden    : kw='isHidden' path (EQ formula_atom)? ;
test_readonly  : kw='isReadonly' path ;
