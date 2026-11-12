% Values of discrete slots and the inputs that fix them.
%
% Options are terms o(E,O), truth values b(true) and b(false). Numbers and texts are not represented, the
% propagator computes them. Their slots only carry the definedness atom defined(X).
%   option(E,O,Ord)    option O of enumeration E at position Ord
%   attr(E,O,A,V)      the value of attribute A of option O, n("1.5") for numbers and t("...") for texts

#defined option/3.

1 { val(X,o(E,O)) : option(E,O,_) } 1 :- sx(X), skind(X,enum(E)).
1 { val(X,b(true)); val(X,b(false)) } 1 :- sx(X), skind(X,bool).

sx(X) :- given_val(X,_).
:- given_val(X,V), not val(X,V).

defined(X) :- given_num(X).
