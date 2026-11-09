// COOM language 1.0, shared parser rules.
grammar Base;
import Tokens;

constant : floating | name | 'true' | 'false' ;
floating : '-'? (FLOATING | INTEGER) ;

// Path expressions address features along the product hierarchy.
path       : path_item ('.' path_item)* ;
path_item  : name ('[' path_index ('..' path_index)? ']')? ;
path_index : INTEGER | ('last' ('-' INTEGER)?) ;

name : NAME | FUNCTION ;

// A statement ends with ';' or with a line break. Line breaks are hidden tokens, see newlineBefore().
stmt_end  : ';' | {newlineBefore()}? ;
same_line : {!newlineBefore()}? ;

compare : '<' | '<=' | '>' | '>=' | EQ | '!=' ;
