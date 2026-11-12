% Defaults, applied greedily.
%
%   default(B,L)          behavior B is a default decided at heuristic level L, higher levels first
%   ddefault(B,T,V)       a default for discrete slots, numeric ones are producers of kind default
%   defaults              present when defaults take part in solving
%
% The domain heuristic prefers applying defaults, higher priorities first. The first model found is therefore a
% greedy approximation of the maximal application of defaults, not the lexicographic optimum.

#defined default/2.
#defined ddefault/3.
#defined defaults/0.

applicable(B,O) :- default(B,_), fires(B,O).
{ applied(B,O) } :- applicable(B,O), defaults.
#heuristic applied(B,O) : default(B,L). [L, true]

dvalue(B,O,W) :- ddefault(B,_,V), applied(B,O), const(V,W).
dvalue(B,O,W) :- ddefault(B,_,V), applied(B,O), pval(V,O,W).
:- ddefault(B,_,_), applied(B,O), not dvalue(B,O,_).
sx(X) :- ddefault(B,T,_), dvalue(B,O,_), tgt(T,O,X).
:- ddefault(B,T,_), dvalue(B,O,W), tgt(T,O,X), not val(X,W).

% A numeric default is applied only together with its value.
:- producer(P,B,default,_,_), applied(B,O), not valued(P,O).
