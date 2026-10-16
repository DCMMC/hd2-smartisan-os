/* Small ARM EABI crash probe, independent of the Android/glibc runtimes.
 * Syscall/ptrace numbers match sources/kernel-tytung/arch/arm/include/asm.
 * Usage: hd2-syscall-trace /absolute/program [args...]
 */
typedef unsigned long U;
static long sc(long n, U a, U b, U c, U d) {
    register U r0 __asm__("r0")=a, r1 __asm__("r1")=b;
    register U r2 __asm__("r2")=c, r3 __asm__("r3")=d;
    register U r7 __asm__("r7")=n;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r3),"r"(r7) : "memory");
    return r0;
}
static void out(const char *s) { U n=0; while(s[n]) ++n; sc(4,1,(U)s,n,0); }
static void hex(U v) { char b[10]; int i; for(i=7;i>=0;--i){b[i]="0123456789abcdef"[v&15];v>>=4;} b[8]=' ';b[9]=0;out(b); }
static void remote_string(U pid, U addr) {
    U word=0,i,j; char b[5];
    for(i=0;i<128;i+=4) {
        if(sc(26,2,pid,addr+i,(U)&word)<0) break;
        for(j=0;j<4;++j) { b[j]=(word>>(j*8))&255; if(!b[j]){b[j]=0;out(b);return;} }
        b[4]=0;out(b);
    }
}
int trace_main(U *sp) {
    U argc=sp[0], status, regs[18], count=0, i; long pid;
    char **argv=(char **)(sp+1), **env=argv+argc+1;
    if(argc<2){out("usage: hd2-syscall-trace /program [args]\n");return 2;}
    pid=sc(2,0,0,0,0);
    if(pid==0){sc(26,0,0,0,0);sc(11,(U)argv[1],(U)(argv+1),(U)env,0);sc(1,127,0,0,0);}
    if(pid<0){out("fork failed\n");return 2;}
    while(sc(114,pid,(U)&status,0,0)>0) {
        if((status&255)!=127){out("exit status ");hex(status);out("\n");break;}
        if(sc(26,12,pid,0,(U)regs)<0){out("GETREGS failed\n");break;}
        out("stop ");hex((status>>8)&255);out("sys ");hex(regs[7]);
        out("r0-r3 ");for(i=0;i<4;++i)hex(regs[i]);out("pc ");hex(regs[15]);
        if(regs[7]==5 && (long)regs[0]>0){out("path ");remote_string(pid,regs[0]);}
        out("\n");
        if(((status>>8)&255)!=5 || ++count>2000){
            out("registers ");for(i=0;i<18;++i)hex(regs[i]);out("\n");
            sc(26,8,pid,0,0);sc(114,pid,(U)&status,0,0);break;
        }
        if(sc(26,24,pid,0,0)<0){out("SYSCALL failed\n");break;}
    }
    return 0;
}
__asm__(".global _start\n_start:\nmov r0, sp\nbl trace_main\nmov r7, #1\nsvc 0\n");
