// COOM language 1.0, behavioral knowledge.
grammar Behavior;
import Base, Formula, Condition;

behavior : kw='behavior' name? behavior_block ;

behavior_block :
    '{'
        (define stmt_end)*
        (conditioned (stmt_end conditioned)*)?
    '}' ;

define : 'define' name EQ formula ;

// A statement with its optional explanation and preconditions. A nested block shares the preconditions.
conditioned :
    explanation?
    precondition*
    ( behavior_block
    | assign_default
    | assign_imply
    | optimize
    | visibility
    | require
    | combinations
    | derivation_table
    ) ;

explanation  : 'explanation' name ;
precondition : 'condition' condition ;

combinations :
    kw='combinations' '(' formula (','? formula)* ')' stmt_end
    (combination_row (stmt_end combination_row)*)? ;
combination_row  : rowType=('allow' | 'forbid') '(' combination_item (','? combination_item)* ')' ;
combination_item : any='-*-' | '(' combination_atom (','? combination_atom)* ')' | combination_atom ;
combination_atom : operator=compare? formula ;

derivation_table :
    kw=('require' | 'default')
    assignment_columns=derivation_table_columns
    ('condition' condition_columns=derivation_table_columns)? stmt_end
    (derivation_table_row (stmt_end derivation_table_row)*)? ;
derivation_table_columns : '(' formula (','? formula)* ')' ;
derivation_table_row :
    '(' derivation_table_atom (','? derivation_table_atom)* ')'
    // condition cells stay on the row's line, otherwise they would start the next row
    (same_line '(' derivation_condition_cell (','? derivation_condition_cell)* ')')? ;
derivation_condition_cell :
      any='-*-'
    | '(' derivation_table_atom (','? derivation_table_atom)* ')'
    | derivation_table_atom ;
derivation_table_atom : operator=compare? formula ;

assign_default : kw='default' ('/' priority=INTEGER)? path EQ formula ;
assign_imply   : kw='imply' path EQ formula ;
optimize       : kw=('minimize' | 'maximize') path ;
visibility     : directive=('readonly' | 'hide') path name* ;
require        : kw='require' condition ;
