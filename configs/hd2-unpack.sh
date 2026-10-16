#!/bin/sh
# First boot of the compressed SD delivery. Never overwrite a running image.
BB=${BB:-/bin/busybox}
dir="$1"
[ -n "$dir" ] && [ -d "$dir" ] || exit 1
image="$dir/rootfs.ext4"
if [ -e "$image" ]; then
    [ "$($BB stat -t "$image" | $BB awk '{print $2}')" = 2147483648 ] || {
        echo 'Existing root image has an unexpected size; leaving it untouched'; exit 1;
    }
    exit 0
fi
[ -f "$image.gz" ] || exit 1
needed=2162688
free=$($BB df -Pk "$dir" | $BB tail -n 1 | $BB awk '{print $4}')
case "$free" in ''|*[!0-9]*) echo 'Cannot determine free SD space'; exit 1;; esac
[ "$free" -ge "$needed" ] || { echo 'Need 2.1 GiB free for first-boot extraction'; exit 1; }
echo 'FIRST BOOT: decompressing rootfs.ext4.gz; keep power connected. ADB is available.'
if ! $BB gzip -dc "$image.gz" > "$image.unpacking"; then
    echo 'Decompression failed; compressed source retained for retry'
    $BB rm -f "$image.unpacking"
    exit 1
fi
[ "$($BB stat -t "$image.unpacking" | $BB awk '{print $2}')" = 2147483648 ] || {
    echo 'Unexpected decompressed image size'; $BB rm -f "$image.unpacking"; exit 1;
}
$BB sync
$BB mv "$image.unpacking" "$image" || exit 1
$BB sync
echo 'Decompression complete; the compressed source is retained for recovery.'
