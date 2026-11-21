#pragma once
#include <Headers/kern_patcher.hpp>

class CPUFriendPlugin {
public:
    void init();
private:
    void patchKext(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size);
    void patchRecovery();
    void patchVceGuard();

    mach_vm_address_t amdAddress {};
    size_t amdSize {};
    bool ioAccelVerified {};
    bool recoveryApplied {};
    bool vceGuardApplied {};
};
