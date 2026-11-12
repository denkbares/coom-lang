% Defaults, applied greedily.
%
%   default(B,L)          behavior B is a default decided at heuristic level L, higher levels first
%   defaults              present when defaults take part in solving
%
% The domain heuristic prefers applying defaults, higher priorities first. The first model found is therefore a
% greedy approximation of the maximal application of defaults, not the lexicographic optimum.

#defined default/2.
#defined defaults/0.

{ applied(B,O) } :- default(B,_), fires(B,O), defaults.
#heuristic applied(B,O) : default(B,L). [L, true]

% A default is applied only together with its value.
:- assign(A,B,default,T,_), path_kind(T,discrete), applied(B,O), not assigned(A,O,_).
:- assign(A,B,default,T,_), path_kind(T,numeric), applied(B,O), not valued(A,O).
