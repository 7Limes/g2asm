from rply import LexerGenerator

def build_lexer():
    lg = LexerGenerator()
    lg.add('DEFINE', r'define')
    lg.add('LOAD', r'load')
    lg.add('DATA_TYPE', '(file|bytes|string)')
    lg.add('DATA_OP', '(raw|pack)')
    lg.add('META_VAR', r'#[A-z]+')
    lg.add('META_CONST', r'(WIDTH|HEIGHT|MEMORY)')

    lg.add('INT', r'-?(?:(?:0x[\dA-Fa-f]+)|(?:0b[01]+)|(?:\d+))')
    lg.add('STRING', r'([\'\"\`])(.*)\1')

    lg.add('LABEL', r'[A-z0-9_]+:')
    lg.add('NAME', r'[A-z_][A-z0-9_]*')

    lg.add('COMMENT', r';.*')
    lg.ignore(r'\s+')
    
    return lg.build()

G2_LEXER = build_lexer()
