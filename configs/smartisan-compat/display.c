/* ARM EABI bridge for the HD2 Adreno driver's pre-4.2 display API.
 * getBuiltInDisplay returns a non-trivial sp<IBinder> through hidden r0;
 * the display ID is in r1. These declarations preserve that binary ABI.
 * The real sp destructor releases the returned strong reference.
 */
extern void get_display(void **token, int id)
    __asm__("_ZN7android21SurfaceComposerClient17getBuiltInDisplayEi");
extern int display_info(const void *token, void *info)
    __asm__("_ZN7android21SurfaceComposerClient14getDisplayInfoERKNS_2spINS_7IBinderEEEPNS_11DisplayInfoE");
extern void release_token(void *token)
    __asm__("_ZN7android2spINS_7IBinderEED1Ev");
int legacy_display_info(int id, void *info)
    __asm__("_ZN7android21SurfaceComposerClient14getDisplayInfoEiPNS_11DisplayInfoE");

int legacy_display_info(int id, void *info) {
    void *token = 0;
    get_display(&token, id);
    int result = display_info(&token, info);
    release_token(&token);
    return result;
}
