// Vega UVD descriptor compatibility and bounded firmware-clear recovery.
#include <Headers/kern_api.hpp>
#include <IOKit/IOLib.h>
#include <mach/mach_time.h>
#include <mach-o/loader.h>
#include "CPUFriend.hpp"
#include "UvdRecovery.hpp"

static const char *ioAccelPaths[] = {
    "/System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2"
};
static const char *amdPaths[] = {
    "/System/Library/Extensions/AMDRadeonX5000.kext/Contents/MacOS/AMDRadeonX5000"
};
static const char *hwlibsPaths[] = {
    "/System/Library/Extensions/AMDRadeonX5000HWServices.kext/Contents/PlugIns/AMDRadeonX5000HWLibs.kext/Contents/MacOS/AMDRadeonX5000HWLibs"
};
static KernelPatcher::KextInfo targets[] = {
    {"com.apple.iokit.IOAcceleratorFamily2", ioAccelPaths, arrsize(ioAccelPaths), {}, {}, KernelPatcher::KextInfo::Unloaded},
    {"com.apple.kext.AMDRadeonX5000", amdPaths, arrsize(amdPaths), {}, {}, KernelPatcher::KextInfo::Unloaded},
    {"com.apple.kext.AMDRadeonX5000HWLibs", hwlibsPaths, arrsize(hwlibsPaths), {}, {}, KernelPatcher::KextInfo::Unloaded}
};

static bool matchesUuid(mach_vm_address_t address, size_t size, const uint8_t (&uuid)[16]) {
    if (size < sizeof(mach_header_64))
        return false;
    auto header = reinterpret_cast<const mach_header_64 *>(address);
    if (header->magic != MH_MAGIC_64 || header->sizeofcmds > size - sizeof(*header))
        return false;
    const auto end = address + sizeof(*header) + header->sizeofcmds;
    auto cursor = address + sizeof(*header);
    for (uint32_t i = 0; i < header->ncmds; ++i) {
        if (end - cursor < sizeof(load_command))
            return false;
        auto command = reinterpret_cast<const load_command *>(cursor);
        if (command->cmdsize < sizeof(*command) || command->cmdsize > end - cursor)
            return false;
        if (command->cmd == LC_UUID && command->cmdsize == sizeof(uuid_command))
            return memcmp(reinterpret_cast<const uuid_command *>(cursor)->uuid, uuid, sizeof(uuid)) == 0;
        cursor += command->cmdsize;
    }
    return false;
}

void CPUFriendPlugin::init() {
    SYSLOG("vegauvd", "Registering descriptor fix and bounded UVD clear for Darwin 24");
    lilu.onKextLoadForce(targets, arrsize(targets),
        [](void *user, KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
            static_cast<CPUFriendPlugin *>(user)->patchKext(patcher, index, address, size);
        }, this);
}

void CPUFriendPlugin::patchKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
    if (address == 0 || size < 32)
        return;
    if (index == targets[0].loadIndex) {
        static const uint8_t expected[] = {0x97,0xa7,0x30,0x5c,0xfb,0x14,0x39,0xfc,0xbc,0x20,0xed,0x83,0x4a,0xbc,0xeb,0x2d};
        ioAccelVerified = matchesUuid(address, size, expected);
        SYSLOG("vegauvd", "IOAccelerator recovery layout verified=%u", ioAccelVerified);
        patchRecovery();
        return;
    }
    if (index == targets[1].loadIndex) {
        static const uint8_t expected[] = {0xca,0x0f,0x82,0xd9,0xaf,0x3c,0x3b,0x51,0xaf,0xef,0xbd,0x09,0x3c,0xb6,0x4a,0x92};
        if (!matchesUuid(address, size, expected)) {
            SYSLOG("vegauvd", "AMD UUID differs; recovery patch refused");
            return;
        }
        amdAddress = address;
        amdSize = size;
        patchRecovery();
        patchVceGuard();
        return;
    }
    if (index != targets[2].loadIndex)
        return;
    // Preserve the existing decoder-enabling patch.
    static const uint8_t find[] = {0x49,0x89,0xfd,0x81,0x3f,0x58,0x03,0x00,0x00,0x75,0x41,0x49,0x8b};
    static const uint8_t replace[] = {0x49,0x89,0xfd,0x81,0x3f,0x48,0x03,0x00,0x00,0x75,0x41,0x49,0x8b};
    auto mem = reinterpret_cast<uint8_t *>(address);
    size_t off = 0;
    if (!KernelPatcher::findPattern(find, nullptr, sizeof(find), mem, size, &off)) {
        SYSLOG("vegauvd", "HWLibs exact signature not found");
        return;
    }
    size_t duplicate = 0;
    if (KernelPatcher::findPattern(find, nullptr, sizeof(find), mem + off + 1, size - off - 1, &duplicate)) {
        SYSLOG("vegauvd", "HWLibs signature non-unique; patch refused");
        return;
    }
    if (KernelPatcher::findAndReplace(mem + off, sizeof(find), find, replace))
        SYSLOG("vegauvd", "HWLibs size check patched 0x358 to 0x348 (offset %lu)", static_cast<unsigned long>(off));
}

void CPUFriendPlugin::patchRecovery() {
    if (recoveryApplied || !ioAccelVerified || amdAddress == 0)
        return;
    // Entire firmware-clear call site in AMDUVDHWEngine::start, 0x793fd..0x7942a.
    static const uint8_t find[] = {
        0x48,0x8d,0xbb,0x40,0x01,0x00,0x00,0x4c,0x8b,0x73,0x20,0xe8,0x67,0xaf,0xfd,0xff,
        0x8b,0x93,0x50,0x01,0x00,0x00,0x4d,0x8b,0x0e,0x4c,0x89,0xf7,0x48,0x89,0xc6,0x31,
        0xc9,0x41,0xb8,0x01,0x00,0x00,0x00,0x41,0xff,0x91,0x48,0x02,0x00,0x00
    };
    static const uint8_t failureExit[] = {0x31,0xc0,0x48,0x83,0xc4,0x10,0x5b,0x41,0x5e,0x5d,0xc3};
    auto memory = reinterpret_cast<uint8_t *>(amdAddress);
    size_t offset = 0, duplicate = 0;
    if (!KernelPatcher::findPattern(find, nullptr, sizeof(find), memory, amdSize, &offset) ||
        KernelPatcher::findPattern(find, nullptr, sizeof(find), memory + offset + 1, amdSize - offset - 1, &duplicate) ||
        amdSize - offset < 0xf5 + sizeof(failureExit) ||
        memcmp(memory + offset + 0xf5, failureExit, sizeof(failureExit)) != 0) {
        SYSLOG("vegauvd", "UVD clear or failure-exit signature differs; recovery patch refused");
        return;
    }

    uint8_t replacement[sizeof(find)];
    memset(replacement, 0x90, sizeof(replacement));
    // mov rdi,rbx; movabs rax,clearFirmware; call rax; test al,al; jz start_failure
    const uint8_t call[] = {0x48,0x89,0xdf,0x48,0xb8};
    memcpy(replacement, call, sizeof(call));
    const auto target = reinterpret_cast<uint64_t>(&UvdRecovery::clearFirmware);
    memcpy(replacement + 5, &target, sizeof(target));
    replacement[13] = 0xff;
    replacement[14] = 0xd0;
    replacement[15] = 0x84;
    replacement[16] = 0xc0;
    replacement[17] = 0x0f;
    replacement[18] = 0x84;
    const int32_t failureBranch = 0xf5 - 23;
    memcpy(replacement + 19, &failureBranch, sizeof(failureBranch));
    recoveryApplied = KernelPatcher::findAndReplace(memory + offset, sizeof(find), find, replacement);
    SYSLOG("vegauvd", "UVD bounded-clear patch applied=%u offset=%lu", recoveryApplied, static_cast<unsigned long>(offset));
}


void CPUFriendPlugin::patchVceGuard() {
    if (vceGuardApplied || amdAddress == 0 || amdSize < 64)
        return;
    // Verified CA0F82D9 AMDVCEHWEngine::start prologue at 0x77dea.
    // Default-deny VCE startup before any firmware or VCELLQ submission:
    // H.264 hardware encode cannot currently initialize reliably on this
    // Monterey-driver/Sequoia-HWLibs combination and has triggered a GPU hang.
    // Hardware UVD decode and HEVC UVD encoder LLQ are left unchanged.
    static const uint8_t signature[] = {
        0x55,0x48,0x89,0xe5,0x41,0x56,0x53,0x48,0x83,0xec,0x10,0x48,0x89,0xfb,
        0x80,0x7f,0x10,0x00,0x74,0x0b,0xff,0x83,0x38,0x01,0x00,0x00,
        0x41,0xb6,0x01,0xeb,0x74
    };
    static const uint8_t before[] = {0x55,0x48,0x89,0xe5};
    static const uint8_t after[] = {0x31,0xc0,0xc3,0x90}; // xor eax,eax; ret; nop
    auto memory = reinterpret_cast<uint8_t *>(amdAddress);
    size_t offset = 0, duplicate = 0;
    if (!KernelPatcher::findPattern(signature, nullptr, sizeof(signature),
                                    memory, amdSize, &offset) ||
        KernelPatcher::findPattern(signature, nullptr, sizeof(signature),
                                   memory + offset + 1, amdSize - offset - 1, &duplicate)) {
        SYSLOG("vegauvd", "VCE safety guard refused: absent or non-unique signature");
        return;
    }
    vceGuardApplied = KernelPatcher::findAndReplace(memory + offset,
                                                     sizeof(before), before, after);
    SYSLOG("vegauvd", "VCE safety guard applied=%u offset=%lu",
           vceGuardApplied, static_cast<unsigned long>(offset));
}
