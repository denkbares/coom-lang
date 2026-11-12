% Three valued conditions.
%
% can(X,O,R) states that condition X at instance O may take the outcome R, one of t, f and i (indefinite). A
% decided condition has one outcome, an open one both t and f. Connectives combine outcomes pointwise with the
% strong Kleene tables. Requirements use can, guards use dt (definitely true) below.
%   dcmp(C,Op,L,R)    comparison of discrete values (options, truth values, instances), decided here
%   leaf(C)           comparison or definedness test over numbers or texts, decided by the propagator
%   isdef(X,P)        a bare path read as a condition
%   cnot(X,A), conj(X) with cand(X,Y), disj(X) with cor(X,Y), cbool(X,true|false)

#defined dcmp/4.
#defined leaf/1.
#defined isdef/2.
#defined cnot/2.
#defined conj/1.
#defined cand/2.
#defined disj/1.
#defined cor/2.
#defined cbool/2.
#defined falsy/1.

% Discrete comparisons. A range side is compared universally, a missing scalar side leaves the comparison open.
side(C,O,l,W) :- dcmp(C,_,L,_), at(C,O), pval(L,O,W).
side(C,O,l,W) :- dcmp(C,_,L,_), at(C,O), const(L,W).
side(C,O,r,W) :- dcmp(C,_,_,R), at(C,O), pval(R,O,W).
side(C,O,r,W) :- dcmp(C,_,_,R), at(C,O), const(R,W).
scalar(C,l) :- dcmp(C,_,L,_), not prange(L).
scalar(C,r) :- dcmp(C,_,_,R), not prange(R).
present(C,O,D) :- side(C,O,D,_).
dopen(C,O) :- dcmp(C,_,_,_), at(C,O), scalar(C,D), not present(C,O,D).
dopen(C,O) :- dcmp(C,_,_,_), at(C,O), not scalar(C,l), not scalar(C,r).

pair(C,O,V,W) :- side(C,O,l,V), side(C,O,r,W), not dopen(C,O).
same(C,O,o(E,A),o(E,B)) :- pair(C,O,o(E,A),o(E,B)).
same(C,O,b(A),b(B)) :- pair(C,O,b(A),b(B)).
same(C,O,V,W) :- pair(C,O,V,W), inst(V,_), inst(W,_).

eqr(C,O,V,W,t) :- same(C,O,V,W), V = W.
eqr(C,O,V,W,f) :- same(C,O,V,W), V != W.
eqr(C,O,V,W,i) :- pair(C,O,V,W), not same(C,O,V,W).
res(C,O,V,W,R) :- dcmp(C,eq,_,_), eqr(C,O,V,W,R).
res(C,O,V,W,f) :- dcmp(C,ne,_,_), eqr(C,O,V,W,t).
res(C,O,V,W,t) :- dcmp(C,ne,_,_), eqr(C,O,V,W,f).
res(C,O,V,W,i) :- dcmp(C,ne,_,_), eqr(C,O,V,W,i).

% Options of one enumeration are ordered by their position, other values have no order.
ord(C,O,o(E,A),o(E,B),X-Y) :- pair(C,O,o(E,A),o(E,B)), option(E,A,X), option(E,B,Y).
ordered(C,O,V,W) :- ord(C,O,V,W,_).
res(C,O,V,W,i) :- dcmp(C,Op,_,_), Op != eq, Op != ne, pair(C,O,V,W), not ordered(C,O,V,W).
res(C,O,V,W,t) :- dcmp(C,lt,_,_), ord(C,O,V,W,D), D < 0.
res(C,O,V,W,f) :- dcmp(C,lt,_,_), ord(C,O,V,W,D), D >= 0.
res(C,O,V,W,t) :- dcmp(C,le,_,_), ord(C,O,V,W,D), D <= 0.
res(C,O,V,W,f) :- dcmp(C,le,_,_), ord(C,O,V,W,D), D > 0.
res(C,O,V,W,t) :- dcmp(C,gt,_,_), ord(C,O,V,W,D), D > 0.
res(C,O,V,W,f) :- dcmp(C,gt,_,_), ord(C,O,V,W,D), D <= 0.
res(C,O,V,W,t) :- dcmp(C,ge,_,_), ord(C,O,V,W,D), D >= 0.
res(C,O,V,W,f) :- dcmp(C,ge,_,_), ord(C,O,V,W,D), D < 0.

dres(C,O,f) :- res(C,O,_,_,f).
dres(C,O,i) :- res(C,O,_,_,i), not dres(C,O,f).
dres(C,O,t) :- dcmp(C,_,_,_), at(C,O), not dopen(C,O), not dres(C,O,f), not dres(C,O,i).
can(C,O,R) :- dres(C,O,R).
can(C,O,t) :- dopen(C,O).
can(C,O,f) :- dopen(C,O).

% Numeric and text leaves. Their outcome is a free choice, which the propagator fixes to the outcome of the
% evaluation. True and false need the operands to be ready, which requires their definedness, so a value cannot
% justify a guard that produces it. Indefinite needs no readiness, since a fault is known before every operand is
% there and an indefinite outcome can only block a guard or fail a requirement.
ready(C,O) :- leaf(C), at(C,O), ready(Y,O) : arg(C,Y).
{ th(C,O,t); th(C,O,f) } 1 :- leaf(C), ready(C,O).
{ th(C,O,i) } :- leaf(C), at(C,O).
:- th(C,O,i), th(C,O,t).
:- th(C,O,i), th(C,O,f).
can(C,O,R) :- th(C,O,R).
open(C,O) :- leaf(C), at(C,O), not th(C,O,t), not th(C,O,f), not th(C,O,i).
can(C,O,t) :- open(C,O).
can(C,O,f) :- open(C,O).

% A bare path holds if it addresses a truthy value. It stays open while a required numeric slot waits. Whether a
% text is blank is decided by the propagator, blank texts in attributes are given as falsy(V).
{ blank(X) } :- defined(X), skind(X,text).
truthy(X,O) :- isdef(X,P), pval(P,O,W), not numeric(W), W != b(false), not falsy(W).
truthy(X,O) :- isdef(X,P), pval(P,O,W), numeric(W), defined(W), not blank(W).
waiting(X,O) :- isdef(X,P), pval(P,O,W), numeric(W), not defined(W), not truthy(X,O).
can(X,O,t) :- truthy(X,O).
can(X,O,t) :- waiting(X,O).
can(X,O,f) :- waiting(X,O).
can(X,O,f) :- isdef(X,_), at(X,O), not truthy(X,O), not waiting(X,O).

% Connectives.
can(X,O,t) :- cnot(X,A), can(A,O,f).
can(X,O,f) :- cnot(X,A), can(A,O,t).
can(X,O,i) :- cnot(X,A), can(A,O,i).

tori(Y,O) :- can(Y,O,t).
tori(Y,O) :- can(Y,O,i).
fori(Y,O) :- can(Y,O,f).
fori(Y,O) :- can(Y,O,i).

can(X,O,t) :- conj(X), at(X,O), can(Y,O,t) : cand(X,Y).
can(X,O,f) :- cand(X,Y), can(Y,O,f).
can(X,O,i) :- cand(X,Y), can(Y,O,i), tori(Z,O) : cand(X,Z).

can(X,O,t) :- cor(X,Y), can(Y,O,t).
can(X,O,f) :- disj(X), at(X,O), can(Y,O,f) : cor(X,Y).
can(X,O,i) :- cor(X,Y), can(Y,O,i), fori(Z,O) : cor(X,Z).

can(X,O,t) :- cbool(X,true), at(X,O).
can(X,O,f) :- cbool(X,false), at(X,O).

% Definitely true and definitely false, derived bottom up from the decided leaves. A connective is definitely true
% exactly when its outcomes are {t}, but derived this way a guard holds only through operands that are themselves
% decided, so an open operand cannot lend it support while a value it produces rules out the other outcomes.
dt(C,O) :- dres(C,O,t).
df(C,O) :- dres(C,O,f).
dt(C,O) :- th(C,O,t).
df(C,O) :- th(C,O,f).
dt(X,O) :- truthy(X,O).
df(X,O) :- isdef(X,_), at(X,O), not truthy(X,O), not waiting(X,O).
dt(X,O) :- cnot(X,A), df(A,O).
df(X,O) :- cnot(X,A), dt(A,O).
dt(X,O) :- conj(X), at(X,O), dt(Y,O) : cand(X,Y).
df(X,O) :- cand(X,Y), df(Y,O).
dt(X,O) :- cor(X,Y), dt(Y,O).
df(X,O) :- disj(X), at(X,O), df(Y,O) : cor(X,Y).
dt(X,O) :- cbool(X,true), at(X,O).
df(X,O) :- cbool(X,false), at(X,O).
