% Values of discrete slots and the inputs that fix them.
%
% Options are terms o(E,O), truth values b(true) and b(false). Numbers and texts are not represented, the
% propagator computes them. Their slots only carry the definedness atom defined(X).
%   option(E,O,Ord)        option O of enumeration E at position Ord
%   attribute(E,O,A,V)     the value of attribute A of option O, n("1.5") for numbers and t("...") for texts

#defined option/3.

1 { value(X,o(E,O)) : option(E,O,_) } 1 :- exists(X), kind(X,enum(E)).
1 { value(X,b(true)); value(X,b(false)) } 1 :- exists(X), kind(X,bool).

exists(X) :- input(X,_).
:- input(X,V), not value(X,V).

defined(X) :- input(X), numeric(X).
