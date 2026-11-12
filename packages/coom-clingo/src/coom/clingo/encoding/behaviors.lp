% Behaviors: preconditions, requirements, tables and implications.
%
%   beh(B,S), cond(B,X)        behavior B of structure S with its preconditions
%   require(B,X)               the condition X must be possibly true, tables are lowered to it
%   dimply(B,T,V)              the discrete slots of path T hold the value of V
%   producer(P,B,Kind,T,X)     the numeric or text slots of path T take the value of formula X, Kind being
%                              imply, default or require (a determining equality)

#defined beh/2.
#defined cond/2.
#defined require/2.
#defined dimply/3.
#defined producer/5.

% A behavior fires where all its preconditions are definitely true.
fires(B,O) :- beh(B,S), inst(O,S), ex(O), dt(X,O) : cond(B,X).

% A requirement fails its candidate when it cannot become true.
:- require(B,X), fires(B,O), not can(X,O,t).

% Discrete implications create their target slot and fix its value.
ivalue(B,O,W) :- dimply(B,_,V), fires(B,O), const(V,W).
ivalue(B,O,W) :- dimply(B,_,V), fires(B,O), pval(V,O,W).
sx(X) :- dimply(B,T,_), ivalue(B,O,_), tgt(T,O,X).
:- dimply(B,T,_), ivalue(B,O,W), tgt(T,O,X), not val(X,W).

% A producer is active when its behavior fires, or its default is applied, and is on once its formula is ready.
% Readiness is necessary for a value but not sufficient, an aggregate over nothing has none. The propagator decides
% valued(P,O) by evaluating the formula, and only valued producers define their target slots. Every defined value is
% therefore founded on the definedness of what its formula reads.
pact(P,O) :- producer(P,B,imply,_,_), fires(B,O).
pact(P,O) :- producer(P,B,require,_,_), fires(B,O).
pact(P,O) :- producer(P,B,default,_,_), applied(B,O).
on(P,O) :- pact(P,O), producer(P,_,_,_,X), ready(X,O).
{ valued(P,O) } :- on(P,O).
defined(Y) :- valued(P,O), producer(P,_,_,T,_), tgt(T,O,Y).
