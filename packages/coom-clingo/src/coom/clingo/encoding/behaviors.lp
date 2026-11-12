% Behaviors: preconditions, requirements, tables and assigns.
%
%   behavior(B,S), precondition(B,X)   behavior B of structure S with its preconditions
%   require(B,X)                       the condition X must be possibly true, tables are lowered to it
%   assign(A,B,Kind,T,V)               assign A of behavior B writes the value of V into the slots of path T, Kind
%                                      being imply, default or require (a determining equality)

#defined behavior/2.
#defined precondition/2.
#defined require/2.
#defined assign/5.

% A behavior fires where all its preconditions are satisfied.
fires(B,O) :- behavior(B,S), instance(O,S), exists(O), sat(X,O) : precondition(B,X).

% A requirement fails its candidate when it cannot become true.
:- require(B,X), fires(B,O), not may_be(X,O,true).

% An assign is active when its behavior fires, or for a default when the default is applied.
active(A,O) :- assign(A,B,imply,_,_), fires(B,O).
active(A,O) :- assign(A,B,require,_,_), fires(B,O).
active(A,O) :- assign(A,B,default,_,_), applied(B,O).

% Discrete assigns create their target slot and fix its value.
assigned(A,O,W) :- assign(A,_,_,T,V), path_kind(T,discrete), active(A,O), constant(V,W).
assigned(A,O,W) :- assign(A,_,_,T,V), path_kind(T,discrete), active(A,O), path_value(V,O,W).
exists(X) :- assigned(A,O,_), assign(A,_,_,T,_), target(T,O,X).
:- assigned(A,O,W), assign(A,_,_,T,_), target(T,O,X), not value(X,W).

% A numeric or text assign can hold a value once its formula is ready. Readiness is necessary for a value but not
% sufficient, an aggregate over nothing has none. The propagator decides valued(A,O) by evaluating the formula, and
% only valued assigns define their target slots. Every defined value is therefore founded on the definedness of what
% its formula reads.
{ valued(A,O) } :- active(A,O), assign(A,_,_,T,X), path_kind(T,numeric), ready(X,O).
defined(Y) :- valued(A,O), assign(A,_,_,T,_), target(T,O,Y).
