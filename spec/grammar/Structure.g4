// COOM language 1.0, structural declarations.
grammar Structure;
import Base;

product :
    kw='product' '{'
        (feature (stmt_end feature)*)?
    '}' ;

structure :
    kw='structure' name '{'
        (feature (stmt_end feature)*)?
    '}' ;

enumeration :
    kw='enumeration' name '{'
        ((attribute | option) (stmt_end (attribute | option))*)?
    '}' ;

feature     : cardinality? field ;
cardinality : min=INTEGER (range='..' (max=(INTEGER | '*'))?)? ;

attribute : kw='attribute' field ;
option    : name (EQ '(' constant (','? constant)* ')')? ;

field      : (number_def fieldName=name) | (string_def fieldName=name) | ((type_ref=name)? fieldName=name) ;
number_def : kw='num' fraction? unit? (min=bound '-' max=bound)? ;
// An open bound of a range is written as '*'.
bound      : floating | open='*' ;
string_def : kw='string' ;

// Fraction digits: '.##' is a grid of two digits, '.*' is the eight digit grid.
fraction : '.' digits=(HASHES | '*') ;
unit     : '/' text=(NAME | FLOATING | INTEGER | HASHES | FUNCTION) ;
