// VegaUVDAbiFix proof-of-concept: patch only Sequoia 15.x HWLibs descriptor-size check.
// Offline candidate. Do not deploy without recovery plan and explicit reboot approval.
#include <Headers/kern_api.hpp>
#include "CPUFriend.hpp"

static const char *hwlibsPaths[] = {
    "/System/Library/Extensions/AMDRadeonX5000HWServices.kext/Contents/PlugIns/AMDRadeonX5000HWLibs.kext/Contents/MacOS/AMDRadeonX5000HWLibs"
};
static KernelPatcher::KextInfo hwlibs[] = {
    {"com.apple.kext.AMDRadeonX5000HWLibs", hwlibsPaths, arrsize(hwlibsPaths), {}, {}, KernelPatcher::KextInfo::Unloaded}
};

void CPUFriendPlugin::init() {
    SYSLOG("vegauvd", "Registered HWLibs on-load patch for Darwin 24");
    lilu.onKextLoadForce(hwlibs, arrsize(hwlibs),
        [](void *user, KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
            static_cast<CPUFriendPlugin *>(user)->patchKext(patcher, index, address, size);
        }, this);
    SYSLOG("vegauvd", "HWLibs on-load callback registration requested");
}

void CPUFriendPlugin::patchKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size) {
    if (index != hwlibs[0].loadIndex || address == 0 || size < 32) return;
    static const uint8_t find[] = {0x49,0x89,0xfd,0x81,0x3f,0x58,0x03,0x00,0x00,0x75,0x41,0x49,0x8b};
    static const uint8_t replace[] = {0x49,0x89,0xfd,0x81,0x3f,0x48,0x03,0x00,0x00,0x75,0x41,0x49,0x8b};
    auto mem = reinterpret_cast<uint8_t *>(address);
    size_t off = 0;
    if (!KernelPatcher::findPattern(find, nullptr, sizeof(find), mem, size, &off)) {
        SYSLOG("vegauvd", "HWLibs exact signature not found; no patch applied");
        return;
    }
    size_t off2 = 0;
    if (off + 1 < size && KernelPatcher::findPattern(find, nullptr, sizeof(find), mem + off + 1, size - off - 1, &off2)) {
        SYSLOG("vegauvd", "HWLibs signature non-unique; refusing patch");
        return;
    }
    if (KernelPatcher::findAndReplace(mem, size, find, replace))
        SYSLOG("vegauvd", "HWLibs size check patched 0x358 to 0x348 (offset %lu)", static_cast<unsigned long>(off));
    else
        SYSLOG("vegauvd", "HWLibs size-check patch failed");
}
