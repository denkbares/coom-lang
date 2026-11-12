% Complements of existence and definedness.
%
% Cautious consequences hold the atoms true in every model, so a slot that is absent or a number that is undefined in
% every model needs an atom of its own to show up among them. Their only use is deciding which computed values are
% the same in every completion.

absent(X) :- slot(X,_,_,_), not exists(X).
undefined(X) :- slot(X,_,_,_), numeric(X), not defined(X).
