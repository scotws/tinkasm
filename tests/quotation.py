# Test for string / semicolon 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 16. Feb 2017
# This version: 16. Feb 2017

teststrings = [ '.byte = "frog", "frog" ; comment', 
    '.byte = "this; that", "slick"', 
    '.byte = "this that", "that ; this" ; comment ;',
    '.byte = "this that", "that ;; this" ; comment',
    ".byte = 'a', ';', 'a' ; comment",
    '.byte = "this; that", "slick" ; comment']


for ts in teststrings:

    ls = len(ts)
    dq_count = 0
    sq_count = 0
    normal = ''
    comment = ''

    for i in range(ls):
        
        if ts[i] == '"':
            dq_count += 1
            continue

        if ts[i] == "'":
            sq_count += 1
            continue


        if ts[i] == ';':
            
            if (dq_count % 2 == 0) and (sq_count % 2 == 0):
                
                normal = ts[:i]
                comment = ts[i+1:].strip()
                break

    if normal == '':
        normal = ts
        comment = ''

    print(ts) 
    print('   Normal:', normal)
    print('   Comment:', comment)
    print()
