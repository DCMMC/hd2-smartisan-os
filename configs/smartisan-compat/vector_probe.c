/* On-device ordered insertion/merge probe for both vtable layouts. */
extern void construct(void *, unsigned, unsigned)
    __asm__("_ZN7android16SortedVectorImplC1Ejj");
extern int add(void *, const void *) __asm__("_ZN7android16SortedVectorImpl3addEPKv");
extern int merge(void *, const void *)
    __asm__("_ZN7android16SortedVectorImpl5mergeERKS0_");
extern void finish(void *) __asm__("_ZN7android10VectorImpl13finish_vectorEv");
extern void reserved(void *) __asm__("_ZN7android10VectorImpl19reservedVectorImpl1Ev");
extern int write(int, const void *, unsigned);
extern void _exit(int);
extern void *memmove(void *, const void *, unsigned);

typedef unsigned word;
struct vector { word fields[5]; };
static int compare(void *self, const int *a, const int *b) {
    (void)self;
    return (*a > *b) - (*a < *b);
}
static void noop(void *self, void *items, unsigned n) { (void)self; (void)items; (void)n; }
static void copy(void *self, void *dst, const void *src, unsigned n) {
    (void)self; memmove(dst,src,n*sizeof(int));
}
static void splat(void *self, int *dst, const int *src, unsigned n) {
    (void)self; while (n--) *dst++=*src;
}
static void init(struct vector *v, word *table, int legacy) {
    construct(v, sizeof(int), 7);
    v->fields[0] = (word)table;
    table[2]=(word)noop; table[3]=(word)noop; table[4]=(word)copy;
    table[5]=(word)splat; table[6]=(word)copy; table[7]=(word)copy;
    table[8] = (word)(legacy ? (void *)reserved : (void *)compare);
    table[16] = (word)compare;
}
static int check(struct vector *v, const int *expected, int n) {
    if (v->fields[2] != (word)n) return 1;
    int *items = (int *)v->fields[1];
    int i;
    for (i=0; i<n; ++i) if (items[i] != expected[i]) return 2;
    return 0;
}
int main(void) {
    int legacy, order, i;
    for (legacy=0; legacy<2; ++legacy) {
        for (order=0; order<3; ++order) {
            struct vector a, b;
            word av[25]={0}, bv[25]={0};
            int low[2]={1,2}, high[2]={10,20}, odd[2]={1,3}, even[2]={2,4};
            int expected[4]={1,2,10,20}, mixed[4]={1,2,3,4};
            int *aa=order==0 ? high : order==1 ? low : odd;
            int *bb=order==0 ? low : order==1 ? high : even;
            init(&a,av,legacy); init(&b,bv,legacy);
            for (i=1;i>=0;--i) { add(&a,&aa[i]); add(&b,&bb[i]); }
            if (merge(&a,&b)<0 || check(&a,order==2 ? mixed : expected,4)) {
                write(1,"VECTOR FAIL\n",12); _exit(1);
            }
            finish(&a); finish(&b);
        }
    }
    write(1,"Both vector ABIs: insertion and all merge branches passed\n",57);
    _exit(0);
}
