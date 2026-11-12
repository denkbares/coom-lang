% Existence of instances and slots.
%
% The potential instances and slots come from instances.lp. Inputs of the configuration:
%   input(X)       the input holds the instance of slot X, or a number or text the propagator knows
%   input(X,V)     the input selects the option or truth value V for slot X
%
% A slot term doubles as the term of its instance, so exists(X) is the existence of both.

#defined input/1.
#defined input/2.

exists(root).

kind(X,K) :- slot(X,N,F,_), instance(N,S), kind(S,F,K).
numeric(X) :- kind(X,num).
numeric(X) :- kind(X,text).

% A slot is potential while its instance exists and required below the minimum cardinality.
potential(X) :- slot(X,N,_,_), exists(N).
required(X) :- slot(X,N,F,I), instance(N,S), feature(S,F,Min,_), I < Min.

% Required slots exist, optional discrete slots are chosen, numeric and text slots exist by their value.
exists(X) :- potential(X), required(X).
{ exists(X) } :- potential(X), not required(X), not numeric(X).
exists(X) :- potential(X), numeric(X), defined(X).
exists(X) :- input(X), not numeric(X).

% Discrete slots are filled from the front, so a slot implies its predecessor.
exists(s(N,F,I-1)) :- exists(s(N,F,I)), I > 0, not numeric(s(N,F,I)).
