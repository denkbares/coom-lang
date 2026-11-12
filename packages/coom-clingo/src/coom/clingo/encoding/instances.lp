% The potential instances and their slots, unrolled up to the maximum cardinalities.
%
%   feature(S,F,Min,Max) and kind(S,F,K) with K one of struct(T), enum(E), bool, num, text
%
% The product instance is root. Every slot is a term s(N,F,I) for index I of feature F of the potential instance N,
% and the slot of a structure feature doubles as the term of the instance it may hold.

#defined feature/4.
#defined kind/3.

inst(root,":root").
slot(s(N,F,I),N,F,I) :- inst(N,S), feature(S,F,_,Max), I = 0..Max-1.
inst(X,T) :- slot(X,N,F,_), inst(N,S), kind(S,F,struct(T)).
