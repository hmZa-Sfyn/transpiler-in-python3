include:<stdio>
int:main = (int:argc|char:*argv[]) => {
   int:x = 100;
   int:y = 250;
   int:z = (x*y);
   loop:for:(int:zx=24|zx<=1000|zx=zx*2) => {
      printf("hello.");
   }
}
