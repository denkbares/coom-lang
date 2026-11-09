// COOM language 1.0, boolean conditions.
grammar Condition;
import Formula;

condition         : condition_or ;
condition_or      : condition_and ('||' condition_and)* ;
condition_and     : condition_not ('&&' condition_not)* ;
condition_not     : '!' condition_not | ('(' condition ')') | condition_compare ;
condition_compare : formula condition_part* ;
condition_part    : operator=compare formula ;
