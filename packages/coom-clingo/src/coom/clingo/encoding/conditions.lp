% Three valued conditions.
%
% may_be(X,O,R) states that condition X at instance O may take the outcome R, one of true, false and indefinite. A
% decided condition has one outcome, an open one both true and false. Connectives combine outcomes pointwise with the
% strong Kleene tables. Requirements use may_be, guards use sat and unsat below.
%   discrete_compare(C,Op,L,R)  comparison of discrete values (options, truth values, instances), decided here
%   leaf(C)                     comparison or definedness test over numbers or texts, decided by the propagator
%   is_defined(X,P)             a bare path read as a condition
%   negation(X,A), and(X) with and(X,Y), or(X) with or(X,Y), constant(X,b(true)) and constant(X,b(false))
%
% An atomic condition takes its outcome truth(C,O,R) once decided and is open(C,O) while it waits for a value.

#defined discrete_compare/4.
#defined leaf/1.
#defined is_defined/2.
#defined negation/2.
#defined and/1.
#defined and/2.
#defined or/1.
#defined or/2.
#defined falsy/1.

:- truth(C,O,R), truth(C,O,S), R < S.
may_be(C,O,R) :- truth(C,O,R).
may_be(C,O,true) :- open(C,O).
may_be(C,O,false) :- open(C,O).

% Discrete comparisons. A range side is compared universally, a missing scalar side leaves the comparison open.
side(C,O,l,W) :- discrete_compare(C,_,L,_), at(C,O), path_value(L,O,W).
side(C,O,l,W) :- discrete_compare(C,_,L,_), at(C,O), constant(L,W).
side(C,O,r,W) :- discrete_compare(C,_,_,R), at(C,O), path_value(R,O,W).
side(C,O,r,W) :- discrete_compare(C,_,_,R), at(C,O), constant(R,W).
scalar(C,l) :- discrete_compare(C,_,L,_), not path_range(L).
scalar(C,r) :- discrete_compare(C,_,_,R), not path_range(R).
present(C,O,D) :- side(C,O,D,_).
open(C,O) :- discrete_compare(C,_,_,_), at(C,O), scalar(C,D), not present(C,O,D).
open(C,O) :- discrete_compare(C,_,_,_), at(C,O), not scalar(C,l), not scalar(C,r).

pair(C,O,V,W) :- side(C,O,l,V), side(C,O,r,W), not open(C,O).
comparable(C,O,o(E,A),o(E,B)) :- pair(C,O,o(E,A),o(E,B)).
comparable(C,O,b(A),b(B)) :- pair(C,O,b(A),b(B)).
comparable(C,O,V,W) :- pair(C,O,V,W), instance(V,_), instance(W,_).

equal(C,O,V,W,true) :- comparable(C,O,V,W), V = W.
equal(C,O,V,W,false) :- comparable(C,O,V,W), V != W.
equal(C,O,V,W,indefinite) :- pair(C,O,V,W), not comparable(C,O,V,W).
result(C,O,V,W,R) :- discrete_compare(C,eq,_,_), equal(C,O,V,W,R).
result(C,O,V,W,false) :- discrete_compare(C,ne,_,_), equal(C,O,V,W,true).
result(C,O,V,W,true) :- discrete_compare(C,ne,_,_), equal(C,O,V,W,false).
result(C,O,V,W,indefinite) :- discrete_compare(C,ne,_,_), equal(C,O,V,W,indefinite).

% Options of one enumeration are ordered by their position, other values have no order.
order(C,O,o(E,A),o(E,B),X-Y) :- pair(C,O,o(E,A),o(E,B)), option(E,A,X), option(E,B,Y).
ordered(C,O,V,W) :- order(C,O,V,W,_).
result(C,O,V,W,indefinite) :- discrete_compare(C,Op,_,_), Op != eq, Op != ne, pair(C,O,V,W), not ordered(C,O,V,W).
result(C,O,V,W,true) :- discrete_compare(C,lt,_,_), order(C,O,V,W,D), D < 0.
result(C,O,V,W,false) :- discrete_compare(C,lt,_,_), order(C,O,V,W,D), D >= 0.
result(C,O,V,W,true) :- discrete_compare(C,le,_,_), order(C,O,V,W,D), D <= 0.
result(C,O,V,W,false) :- discrete_compare(C,le,_,_), order(C,O,V,W,D), D > 0.
result(C,O,V,W,true) :- discrete_compare(C,gt,_,_), order(C,O,V,W,D), D > 0.
result(C,O,V,W,false) :- discrete_compare(C,gt,_,_), order(C,O,V,W,D), D <= 0.
result(C,O,V,W,true) :- discrete_compare(C,ge,_,_), order(C,O,V,W,D), D >= 0.
result(C,O,V,W,false) :- discrete_compare(C,ge,_,_), order(C,O,V,W,D), D < 0.

truth(C,O,false) :- result(C,O,_,_,false).
truth(C,O,indefinite) :- result(C,O,_,_,indefinite), not truth(C,O,false).
truth(C,O,true) :- discrete_compare(C,_,_,_), at(C,O), not open(C,O), not truth(C,O,false), not truth(C,O,indefinite).

% Numeric and text leaves. Their outcome is a free choice, which the propagator fixes to the outcome of the
% evaluation. True and false need the operands to be ready, which requires their definedness, so a value cannot
% justify a guard that produces it. Indefinite needs no readiness, since a fault is known before every operand is
% there and an indefinite outcome can only block a guard or fail a requirement.
ready(C,O) :- leaf(C), at(C,O), ready(Y,O) : operand(C,Y).
{ truth(C,O,true); truth(C,O,false) } :- leaf(C), ready(C,O).
{ truth(C,O,indefinite) } :- leaf(C), at(C,O).
open(C,O) :- leaf(C), at(C,O), not truth(C,O,true), not truth(C,O,false), not truth(C,O,indefinite).

% A bare path holds if it addresses a truthy value. It stays open while a required numeric slot waits. Whether a
% text is blank is decided by the propagator, blank texts in attributes are given as falsy(V).
{ blank(X) } :- defined(X), kind(X,text).
truth(X,O,true) :- is_defined(X,P), path_value(P,O,W), not numeric(W), W != b(false), not falsy(W).
truth(X,O,true) :- is_defined(X,P), path_value(P,O,W), numeric(W), defined(W), not blank(W).
open(X,O) :- is_defined(X,P), path_value(P,O,W), numeric(W), not defined(W), not truth(X,O,true).
truth(X,O,false) :- is_defined(X,_), at(X,O), not truth(X,O,true), not open(X,O).

% Truth value constants.
truth(X,O,true) :- constant(X,b(true)), at(X,O).
truth(X,O,false) :- constant(X,b(false)), at(X,O).

% Connectives. The Kleene tables need to know whether an operand may take an outcome other than false or true.
may_be(X,O,true) :- negation(X,A), may_be(A,O,false).
may_be(X,O,false) :- negation(X,A), may_be(A,O,true).
may_be(X,O,indefinite) :- negation(X,A), may_be(A,O,indefinite).

may_be_other_than(Y,O,false) :- may_be(Y,O,true).
may_be_other_than(Y,O,false) :- may_be(Y,O,indefinite).
may_be_other_than(Y,O,true) :- may_be(Y,O,false).
may_be_other_than(Y,O,true) :- may_be(Y,O,indefinite).

may_be(X,O,true) :- and(X), at(X,O), may_be(Y,O,true) : and(X,Y).
may_be(X,O,false) :- and(X,Y), may_be(Y,O,false).
may_be(X,O,indefinite) :- and(X,Y), may_be(Y,O,indefinite), may_be_other_than(Z,O,false) : and(X,Z).

may_be(X,O,true) :- or(X,Y), may_be(Y,O,true).
may_be(X,O,false) :- or(X), at(X,O), may_be(Y,O,false) : or(X,Y).
may_be(X,O,indefinite) :- or(X,Y), may_be(Y,O,indefinite), may_be_other_than(Z,O,true) : or(X,Z).

% Satisfied and unsatisfied, derived bottom up from the decided atomic conditions. A connective is satisfied exactly
% when its outcomes are {true}, but derived this way a guard holds only through operands that are themselves decided,
% so an open operand cannot lend it support while a value it produces rules out the other outcomes.
sat(C,O) :- truth(C,O,true).
unsat(C,O) :- truth(C,O,false).
sat(X,O) :- negation(X,A), unsat(A,O).
unsat(X,O) :- negation(X,A), sat(A,O).
sat(X,O) :- and(X), at(X,O), sat(Y,O) : and(X,Y).
unsat(X,O) :- and(X,Y), unsat(Y,O).
sat(X,O) :- or(X,Y), sat(Y,O).
unsat(X,O) :- or(X), at(X,O), unsat(Y,O) : or(X,Y).
