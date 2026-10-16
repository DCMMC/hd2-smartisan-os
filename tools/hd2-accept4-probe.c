/* No libc needed: check that ARM EABI accept4 reaches its implementation. */
typedef unsigned long U;
static long call4(long n, U a, U b, U c, U d) {
    register U r0 __asm__("r0")=a, r1 __asm__("r1")=b;
    register U r2 __asm__("r2")=c, r3 __asm__("r3")=d;
    register U r7 __asm__("r7")=n;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r3),"r"(r7) : "memory");
    return r0;
}
void probe(void) {
    long result=call4(366, (U)-1, 0, 0, 0);
    static const char ok[]="accept4: EBADF (implemented)\n";
    static const char missing[]="accept4: ENOSYS (missing)\n";
    static const char other[]="accept4: unexpected result\n";
    if(result==-9) call4(4,1,(U)ok,sizeof(ok)-1,0);
    else if(result==-38) call4(4,1,(U)missing,sizeof(missing)-1,0);
    else call4(4,1,(U)other,sizeof(other)-1,0);
    call4(1,result==-9?0:1,0,0,0);
}
__asm__(".global _start\n_start:\nbl probe\n");
