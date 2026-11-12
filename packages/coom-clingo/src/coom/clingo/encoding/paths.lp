% Evaluation of paths and readiness of formulas.
%
% Every formula and condition node X belongs to a behavior of structure S and is evaluated at each existing
% instance of S, written origin(X,S). A path node P is described by
%   path_start(P,origin|root), path_length(P,L), path_kind(P,discrete|numeric)
%   path_range(P)             the path may address several values
%   path_step(P,K,F,Lo,Hi)    step K follows feature F through the indices Lo..Hi, negative ones counted from the end
%   path_attribute(P,K,A)     step K reads attribute A of the option reached so far
% Other formula nodes are constant(X,V) or compound(X) with their operands operand(X,Y), aggregate(X) marking count,
% sum, min and max.

#defined origin/2.
#defined path_start/2.
#defined path_length/2.
#defined path_kind/2.
#defined constant/2.
#defined compound/1.
#defined aggregate/1.
#defined operand/2.
#defined path_step/5.
#defined path_attribute/3.
#defined path_range/1.
#defined target/1.
#defined attribute/4.

at(X,O) :- origin(X,S), instance(O,S), exists(O).

reach(P,O,0,O) :- at(P,O), path_start(P,origin).
reach(P,O,0,root) :- at(P,O), path_start(P,root).

% Step K of path P leaves the instance V through feature F. The last index of the extent of a feature covers the
% required slots and every existing one.
step(P,O,K,V,F) :- reach(P,O,K-1,V), path_step(P,K,F,_,_), instance(V,_).
needs_last(V,F) :- step(P,O,K,V,F), path_step(P,K,F,Lo,_), Lo < 0.
needs_last(V,F) :- step(P,O,K,V,F), path_step(P,K,F,_,Hi), Hi < 0.
last(V,F,L) :- needs_last(V,F), instance(V,S), feature(S,F,Min,_), L = #max{ I : exists(s(V,F,I)); M : M = Min-1 }.

first(P,O,K,V,Lo) :- step(P,O,K,V,F), path_step(P,K,F,Lo,_), Lo >= 0.
first(P,O,K,V,L+1+Lo) :- step(P,O,K,V,F), path_step(P,K,F,Lo,_), Lo < 0, last(V,F,L).
final(P,O,K,V,Hi) :- step(P,O,K,V,F), path_step(P,K,F,_,Hi), Hi >= 0.
final(P,O,K,V,L+1+Hi) :- step(P,O,K,V,F), path_step(P,K,F,_,Hi), Hi < 0, last(V,F,L).

addresses(P,O,K,X) :- step(P,O,K,V,F), first(P,O,K,V,A), final(P,O,K,V,B), slot(X,V,F,I), A <= I, I <= B, exists(X).

reach(P,O,K,X) :- addresses(P,O,K,X), kind(X,struct(_)).
reach(P,O,K,W) :- addresses(P,O,K,X), value(X,W).
reach(P,O,K,X) :- addresses(P,O,K,X), numeric(X).
reach(P,O,K,W) :- reach(P,O,K-1,o(E,Opt)), path_attribute(P,K,A), attribute(E,Opt,A,W).

path_value(P,O,W) :- reach(P,O,L,W), path_length(P,L).

% The slots an assignable path writes, created if a single slot, existing ones if a range.
target(P,O,X) :- target(P), step(P,O,L,V,F), path_length(P,L), not path_range(P), first(P,O,L,V,I), slot(X,V,F,I).
target(P,O,X) :- target(P), addresses(P,O,L,X), path_length(P,L), path_range(P).

% A formula is ready when every value it reads is there. Ranges wait for their required members only, since
% an optional numeric slot exists exactly when it is defined.
ready(P,O) :- path_value(P,O,_), path_kind(P,discrete), not path_range(P).
ready(P,O) :- at(P,O), path_kind(P,discrete), path_range(P).
ready(P,O) :- path_value(P,O,W), path_kind(P,numeric), not path_range(P), not numeric(W).
ready(P,O) :- path_value(P,O,X), path_kind(P,numeric), not path_range(P), numeric(X), defined(X).
ready(P,O) :- at(P,O), path_kind(P,numeric), path_range(P), defined(X) : path_value(P,O,X), numeric(X).
ready(X,O) :- at(X,O), constant(X,_).
ready(X,O) :- at(X,O), compound(X), ready_operand(X,Y,O) : operand(X,Y).
ready_operand(X,Y,O) :- operand(X,Y), ready(Y,O).

% Aggregates skip operands that are absent, a scalar path that reaches no slot.
path_absent(P,O) :- at(P,O), path_start(P,_), not path_range(P), not path_value(P,O,_).
ready_operand(X,Y,O) :- aggregate(X), operand(X,Y), path_absent(Y,O).
