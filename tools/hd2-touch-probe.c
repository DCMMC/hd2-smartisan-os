/* Inject one HD2 protocol-A swipe through evdev for UI diagnosis.
 * Raw coordinates: x 6..576, y 6..952. Does not bypass any lock credential.
 * Usage: hd2-touch-probe x0 y0 x1 y1
 */
typedef unsigned long U;
static long sc(long n, U a, U b, U c) {
    register U r0 __asm__("r0")=a, r1 __asm__("r1")=b;
    register U r2 __asm__("r2")=c, r7 __asm__("r7")=n;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r7) : "memory");
    return r0;
}
struct event { U sec, usec; unsigned short type, code; int value; };
static void emit(int fd, int type, int code, int value) {
    struct event e; e.sec=0; e.usec=0; e.type=type; e.code=code; e.value=value;
    sc(4,fd,(U)&e,sizeof(e));
}
static int number(const char *p) { int n=0; while(*p>='0' && *p<='9') n=n*10+*p++-'0'; return n; }
int run(U *sp) {
    char **v=(char **)(sp+1); int x0,y0,x1,y1,fd,i,x,y;
    U delay[2]; delay[0]=0; delay[1]=15000000;
    if(sp[0]!=5) return 2;
    x0=number(v[1]); y0=number(v[2]); x1=number(v[3]); y1=number(v[4]);
    if(x0<6||x0>576||x1<6||x1>576||y0<6||y0>952||y1<6||y1>952) return 2;
    fd=sc(5,(U)"/dev/input/event0",1,0); if(fd<0) return 3;
    for(i=0;i<=32;i++) {
        x=x0+(x1-x0)*i/32; y=y0+(y1-y0)*i/32;
        emit(fd,3,0,x); emit(fd,3,1,y); emit(fd,3,24,100); emit(fd,3,28,1);
        emit(fd,1,330,1); emit(fd,3,53,x); emit(fd,3,54,y);
        emit(fd,3,48,100); emit(fd,3,50,0); emit(fd,0,2,0); emit(fd,0,2,0); emit(fd,0,0,0);
        sc(162,(U)delay,0,0);
    }
    emit(fd,3,24,0); emit(fd,3,28,0); emit(fd,1,330,0); emit(fd,3,48,0);
    emit(fd,0,2,0); emit(fd,0,2,0); emit(fd,0,0,0);
    sc(6,fd,0,0); return 0;
}
__asm__(".global _start\n_start:\nmov r0, sp\nbl run\nmov r7, #1\nsvc 0\n");
