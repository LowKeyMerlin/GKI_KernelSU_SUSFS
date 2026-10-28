<div align="center">

# GKI KernelSU SUSFS

GKI kernels with KernelSU and SUSFS, forked from
[WildKernels/GKI_KernelSU_SUSFS](https://github.com/WildKernels/GKI_KernelSU_SUSFS)
with fixes found on the Xiaomi 17.

[![Build](https://github.com/LowKeyMerlin/GKI_KernelSU_SUSFS/actions/workflows/xiaomi_17.yml/badge.svg)](https://github.com/LowKeyMerlin/GKI_KernelSU_SUSFS/actions/workflows/xiaomi_17.yml)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](/LICENSE)

[Install](#install) | [Build](#build-your-own) | [Credits](#credits)

</div>

> [!CAUTION]
> A bad kernel can leave a device unbootable. Back up your data and your stock `boot` image first. To recover, run `fastboot flash boot boot.img`.

## Highlights

- **Boot-tested pins.** BakaSU (ReSukiSU) and SUSFS stay on commits that have booted. Other pins trigger a warning.
- **SUSFS overlays.** The patch applies cleanly to older 6.12 sublevels.
- **Guided installer.** It copies the release and build date from the device, so both slots report one kernel version.

> [!NOTE]
> The kernels are not device specific. The fixes here were verified on the Xiaomi 17 Ultra (`nezha`, Android 16, kernel 6.12). The installer warns on a device it has not seen and does not stop the flash.

## Install

1. Download the zip from [Releases](https://github.com/LowKeyMerlin/GKI_KernelSU_SUSFS/releases), which may not be the newest build. For the newest, open the latest successful run of [Build Kernels (xiaomi_17)](https://github.com/LowKeyMerlin/GKI_KernelSU_SUSFS/actions/workflows/xiaomi_17.yml), sign in to GitHub and download the `*-AnyKernel3` artifact.
2. Flash the zip:

   | Where | How |
   | ----- | --- |
   | Booted, with root | A kernel flasher that supports AnyKernel3, such as Kernel Flasher |
   | Recovery | `adb sideload <zip>` |

3. Reboot and install the matching manager app.

<details>
<summary>What the installer does</summary>

Six steps: device check, kernel check, read boot image, match the other slot, write boot image, result. A single-slot device is matched against its current boot partition. A source that does not look like a stock kernel produces a warning.

Output adapts to recovery, flasher apps and plain terminals. Set `XI_OUTPUT` to `protocol`, `terminal` or `plain` to force a mode.

</details>

## Build your own

Fork the repository and run **Build Kernels (xiaomi_17)** from the Actions tab.

| Input | Default |
| ----- | ------- |
| `kernel_build_version` | `6.12.x-android16` |
| `os_patch_level` | `23,69` (sublevels, dates such as `2025-06`, or `lts`) |
| `commit_mode` | `verified` |

> [!TIP]
> Keep `commit_mode` at `verified` to build only the pinned commits. The generic guide is [docs/build-from-fork.md](/docs/build-from-fork.md).

<details>
<summary>Staying in sync with upstream</summary>

`main` mirrors upstream and is never edited. Everything here is a new file on `xiaomi_17`, so merging upstream does not conflict.

- Workflows are copies named `xiaomi_17*`, merged with upstream by `sync_clones.py`.
- The installer is applied at build time and wraps upstream's `update-binary` and `ak3-core.sh`.
- **Test Installer (xiaomi_17)** runs the installer in QEMU and Cuttlefish.

</details>

## Credits

[WildKernels](https://github.com/WildKernels/GKI_KernelSU_SUSFS), [osm0sis](https://github.com/osm0sis/AnyKernel3) (AnyKernel3), [BakaSU](https://github.com/Baka-SU/BakaSU), [SUSFS](https://gitlab.com/simonpunk/susfs4ksu) and the [Google GKI sources](https://android.googlesource.com/kernel/common/). Licenses are listed in [THIRD_PARTY_NOTICES.md](/THIRD_PARTY_NOTICES.md).

## License

GPL-3.0, see [LICENSE](/LICENSE). The kernel source is GPL-2.0.
