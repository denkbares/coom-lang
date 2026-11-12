% Existence of instances and slots.
%
% The potential instances and slots come from instances.lp. Inputs of the configuration:
%   given(X)           the instance of slot X is part of the input
%   given_val(X,V)     the input selects the option or truth value V for slot X
%   given_num(X)       the input holds a number or text for slot X, the propagator knows which

#defined given/1.
#defined given_val/2.
#defined given_num/1.

ex(root).

skind(X,K) :- slot(X,N,F,_), inst(N,S), kind(S,F,K).
numeric(X) :- skind(X,num).
numeric(X) :- skind(X,text).

% A slot is potential while its instance exists and required below the minimum cardinality.
pslot(X) :- slot(X,N,_,_), ex(N).
req(X) :- slot(X,N,F,I), inst(N,S), feature(S,F,Min,_), I < Min.

% Required slots exist, optional discrete slots are chosen, numeric and text slots exist by their value.
sx(X) :- pslot(X), req(X).
{ sx(X) } :- pslot(X), not req(X), not numeric(X).
sx(X) :- pslot(X), numeric(X), defined(X).
sx(X) :- given(X).

% Discrete slots are filled from the front, so a slot implies its predecessor.
sx(s(N,F,I-1)) :- sx(s(N,F,I)), I > 0, not numeric(s(N,F,I)).

ex(X) :- sx(X), inst(X,_).
