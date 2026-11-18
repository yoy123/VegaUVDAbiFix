#pragma once
#include <Headers/kern_patcher.hpp>

class CPUFriendPlugin {
public:
    void init();
private:
    void patchKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size);
};
