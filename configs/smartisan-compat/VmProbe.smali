.class public LVmProbe;
.super Ljava/lang/Object;
.method public static main([Ljava/lang/String;)V
    .registers 3
    invoke-static {}, Ljava/lang/Runtime;->getRuntime()Ljava/lang/Runtime;
    move-result-object v0
    invoke-virtual {v0}, Ljava/lang/Runtime;->gcAndTrim()V
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "HD2 gcAndTrim bridge passed"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    return-void
.end method
