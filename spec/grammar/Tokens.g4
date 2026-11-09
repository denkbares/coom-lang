// COOM language 1.0, lexer rules.
grammar Tokens;

FUNCTION : 'count'|'min'|'max'|'sum'|'pow'|'sqrt'|'ceil'|'floor'|'round'|'mod'|'log'|'ln'
         | 'sin'|'asin'|'sinh'|'cos'|'acos'|'cosh'|'tan'|'atan'|'tanh' ;

// Reserved for later language versions. They cannot be used as names unless quoted.
RESERVED : 'static'|'reference'|'exists'|'prefer'|'message'|'contains'|'annotation' ;

EQ : '=' ;

// A name is an identifier or a quoted string. Quoting allows any text, including keywords.
NAME : (ALPHA ALPHANUMERIC*) | QUOTED_SINGLE | QUOTED_DOUBLE ;

fragment ALPHA        : [_$\p{L}\p{Nl}\p{Sc}] ;
fragment ALPHANUMERIC : ALPHA | [\p{Nd}\p{Mn}\p{Mc}\p{Pc}] ;

fragment QUOTED_SINGLE : '\'' (ESC | ~['\\\u0000-\u001F])* '\'' ;
fragment QUOTED_DOUBLE : '"'  (ESC | ~["\\\u0000-\u001F])* '"' ;
fragment ESC     : '\\' (["\\/bfnrt] | UNICODE) ;
fragment UNICODE : 'u' HEX HEX HEX HEX ;
fragment HEX     : [0-9a-fA-F] ;
fragment DIGIT   : [0-9] ;

INTEGER  : DIGIT+ ;
FLOATING : DIGIT+ '.' DIGIT+ ;
HASHES   : '#'+ ;

// Whitespace is skipped. Line breaks go to the hidden channel, the parser inspects them to end statements.
WHITESPACE : [ \t]+ -> skip ;
NEWLINE    : '\r'? '\n' -> channel(HIDDEN) ;

COMMENT           : '//' ~[\n\r]* -> channel(HIDDEN) ;
MULTILINE_COMMENT : '/*' ( MULTILINE_COMMENT | . )*? ('*/' | EOF) -> channel(HIDDEN) ;
