% Evaluation of paths and readiness of formulas.
%
% Every formula and condition node X belongs to a behavior of structure S and is evaluated at each existing
% instance of S, written expr(X,S). A path node P is described by
%   pstart(P,origin|root), plen(P,L), prange(P) if it may address several values, pkind(P,disc|num)
%   pstep(P,K,F,Lo,Hi)  step K follows feature F through the indices Lo..Hi, negative ones counted from the end
%   pattr(P,K,A)        step K reads attribute A of the option reached so far
% Other formula nodes are const(X,V) or compound(X) with their operands arg(X,Y), aggregate(X) marking count,
% sum, min and max.

#defined expr/2.
#defined pstart/2.
#defined plen/2.
#defined pkind/2.
#defined const/2.
#defined compound/1.
#defined aggregate/1.
#defined arg/2.
#defined pstep/5.
#defined pattr/3.
#defined prange/1.
#defined target/1.
#defined attr/4.

at(X,O) :- expr(X,S), inst(O,S), ex(O).

reach(P,O,0,O) :- at(P,O), pstart(P,origin).
reach(P,O,0,root) :- at(P,O), pstart(P,root).

% The last index of the extent of a feature covers the required slots and every existing one.
step_at(P,O,K,V,F) :- reach(P,O,K-1,V), pstep(P,K,F,_,_), inst(V,_).
needlast(V,F) :- step_at(P,O,K,V,F), pstep(P,K,F,Lo,_), Lo < 0.
needlast(V,F) :- step_at(P,O,K,V,F), pstep(P,K,F,_,Hi), Hi < 0.
last(V,F,L) :- needlast(V,F), inst(V,S), feature(S,F,Min,_), L = #max{ I : sx(s(V,F,I)); M : M = Min-1 }.

lo(P,O,K,V,Lo) :- step_at(P,O,K,V,F), pstep(P,K,F,Lo,_), Lo >= 0.
lo(P,O,K,V,L+1+Lo) :- step_at(P,O,K,V,F), pstep(P,K,F,Lo,_), Lo < 0, last(V,F,L).
hi(P,O,K,V,Hi) :- step_at(P,O,K,V,F), pstep(P,K,F,_,Hi), Hi >= 0.
hi(P,O,K,V,L+1+Hi) :- step_at(P,O,K,V,F), pstep(P,K,F,_,Hi), Hi < 0, last(V,F,L).

hit(P,O,K,X) :- step_at(P,O,K,V,F), lo(P,O,K,V,A), hi(P,O,K,V,B), slot(X,V,F,I), A <= I, I <= B, sx(X).

reach(P,O,K,X) :- hit(P,O,K,X), skind(X,struct(_)).
reach(P,O,K,W) :- hit(P,O,K,X), val(X,W).
reach(P,O,K,X) :- hit(P,O,K,X), numeric(X).
reach(P,O,K,W) :- reach(P,O,K-1,o(E,Opt)), pattr(P,K,A), attr(E,Opt,A,W).

pval(P,O,W) :- reach(P,O,L,W), plen(P,L).

% The slots an assignable path writes, created if a single slot, existing ones if a range.
tgt(P,O,X) :- target(P), step_at(P,O,L,V,F), plen(P,L), not prange(P), lo(P,O,L,V,I), slot(X,V,F,I).
tgt(P,O,X) :- target(P), hit(P,O,L,X), plen(P,L), prange(P).

% A formula is ready when every value it reads is there. Ranges wait for their required members only, since
% an optional numeric slot exists exactly when it is defined.
ready(P,O) :- pval(P,O,_), pkind(P,disc), not prange(P).
ready(P,O) :- at(P,O), pkind(P,disc), prange(P).
ready(P,O) :- pval(P,O,W), pkind(P,num), not prange(P), not numeric(W).
ready(P,O) :- pval(P,O,X), pkind(P,num), not prange(P), numeric(X), defined(X).
ready(P,O) :- at(P,O), pkind(P,num), prange(P), defined(X) : pval(P,O,X), numeric(X).
ready(X,O) :- at(X,O), const(X,_).
ready(X,O) :- at(X,O), compound(X), operand(X,Y,O) : arg(X,Y).
operand(X,Y,O) :- arg(X,Y), ready(Y,O).

% Aggregates skip operands that are absent, a scalar path that reaches no slot.
absent(P,O) :- at(P,O), pstart(P,_), not prange(P), not pval(P,O,_).
operand(X,Y,O) :- aggregate(X), arg(X,Y), absent(Y,O).
