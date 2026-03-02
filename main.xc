struct:Player = {
   int:id;
   char[50]:name;
   u_long:points;
}

int:main = (int:argc|char:*argv[]) => {
   int:x = 100;
   struct:Player:player1 = Player {.id:0,.name:"whateve"}
   loop:for:(int:zx=24|zx<=1000|zx=zx*2) => {
      printf("hello.");
   }
}