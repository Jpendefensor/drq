trap DAT #0, #0
fang JMP trap
loop MOV fang, @fang+1
JMP loop