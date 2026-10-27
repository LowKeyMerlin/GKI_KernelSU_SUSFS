SUSFS overlays for android16-6.12

The upstream SUSFS patch is used as is, except for per-file diffs that do not fit older
kernels. overlays/<version>/<kernel>/ holds the adapted diffs and a manifest.json with the
sha256 of the upstream diff each one replaces. The susfs-patches action runs
tools/overlay.py, which fails if upstream changed one of those diffs. Kernels without an
overlay get the upstream patch unchanged.

After a SUSFS bump: regenerate the adapted patch (tools/gen.py and verify.py read
kernels/cache), run overlay.py make and check, and update baseline/.
Baseline: susfs4ksu gki-android16-6.12 at 9c9f19d8, not boot-tested.
