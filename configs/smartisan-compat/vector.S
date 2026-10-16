.syntax unified
.thumb
.section .text
.global hd2_vector_compare
.thumb_func
hd2_vector_compare:
    /* r3 is the vtable; r0/r1/r2 are this/lhs/rhs. The CM11
       legacy vtable has eight reserved VectorImpl methods at +32.
       AOSP/Smartisan puts SortedVectorImpl::do_compare at +32. */
    push {r4, lr}
    ldr ip, [r3, #32]
    ldr r4, 1f
2:  add r4, pc
    cmp ip, r4
    it eq
    ldreq ip, [r3, #64]
    blx ip
    /* Original call sites immediately compared the result with zero. */
    cmp r0, #0
    pop {r4, pc}
    .align 2
1:  .word 0xc01b - (0x136c4 + (2b - hd2_vector_compare) + 4)
