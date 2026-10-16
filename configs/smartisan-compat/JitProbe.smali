.class public LJitProbe;
.super Ljava/lang/Object;

.method public static main([Ljava/lang/String;)V
    .registers 9
    invoke-static {}, Ljava/lang/System;->nanoTime()J
    move-result-wide v0
    const/4 v2, 0x0
    const/4 v3, 0x1
    const v4, 0x4c4b40
  :loop
    mul-int/lit8 v3, v3, 0x1f
    xor-int/2addr v3, v2
    add-int/lit8 v2, v2, 0x1
    if-lt v2, v4, :loop
    invoke-static {}, Ljava/lang/System;->nanoTime()J
    move-result-wide v4
    sub-long/2addr v4, v0
    const-wide v0, 0xf4240
    div-long/2addr v4, v0
    sget-object v6, Ljava/lang/System;->out:Ljava/io/PrintStream;
    invoke-virtual {v6, v3}, Ljava/io/PrintStream;->println(I)V
    invoke-virtual {v6, v4, v5}, Ljava/io/PrintStream;->println(J)V
    return-void
.end method
