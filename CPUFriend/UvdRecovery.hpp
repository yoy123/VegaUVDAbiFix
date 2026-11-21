#pragma once

// Private layouts verified against AMD CA0F82D9 and IOAccelerator 97A7305C.
// The caller must validate those Mach-O UUIDs before installing the call site.
namespace UvdRecovery {

constexpr unsigned EventSlots = 8;
constexpr unsigned HardwareChannels = 16;
constexpr uint32_t NoChannel = 0xFFFFFFFFU;
constexpr unsigned ClearTimeoutMs = 2000;

struct Fence {
    uint32_t channel;
    uint32_t stamp;
};

struct Event {
    Fence fences[EventSlots];
};

struct MemsetInfo {
    uint8_t reserved0[0x18] {};
    uint64_t destination {};
    uint8_t reserved1[0x18] {};
    uint32_t length {};
    uint32_t value {};
    uint8_t reserved2[0x10] {};
};

struct BlitOptions {
    uint8_t reserved0[0x20] {};
    Event *event {};
    uint8_t reserved1[0x28] {};
    void *task {};
    uint64_t reserved2 {};
};

static_assert(sizeof(Event) == 0x40, "IOAccelEvent size");
static_assert(sizeof(MemsetInfo) == 0x50, "UBM_MEMSETINFO size");
static_assert(offsetof(MemsetInfo, destination) == 0x18, "destination offset");
static_assert(offsetof(MemsetInfo, length) == 0x38, "length offset");
static_assert(sizeof(BlitOptions) == 0x60, "ABM_OPTIONS size");
static_assert(offsetof(BlitOptions, event) == 0x20, "event offset");
static_assert(offsetof(BlitOptions, task) == 0x50, "task offset");

template <typename T>
inline T field(const void *object, size_t offset) {
    return *reinterpret_cast<const T *>(static_cast<const uint8_t *>(object) + offset);
}

enum class FenceStatus { Complete, Pending, Invalid };

inline FenceStatus fenceStatus(const Event &event,
                               volatile uint32_t * const *hardwareStamps) {
    if (!hardwareStamps)
        return FenceStatus::Invalid;
    bool hasFence = false;
    bool pending = false;
    for (const auto &fence : event.fences) {
        if (fence.channel == NoChannel)
            continue;
        if (fence.channel >= HardwareChannels || !hardwareStamps[fence.channel])
            return FenceStatus::Invalid;
        hasFence = true;
        const uint32_t completed = *hardwareStamps[fence.channel];
        // Match IOAccel's signed difference, including stamp wraparound.
        pending |= static_cast<int32_t>(fence.stamp - completed) > 0;
    }
    if (!hasFence)
        return FenceStatus::Invalid;
    return pending ? FenceStatus::Pending : FenceStatus::Complete;
}

// Invoked only at AMDUVDHWEngine::start's firmware clear call site.
// GPU submission and its stack event follow AMDAtomicBlitManager::doMemset.
// postBlitUpdate copies fence values into the event before submission returns.
inline bool clearFirmware(void *engine) {
    void *handler = field<void *>(engine, 0x20);
    void *mapping = field<void *>(engine, 0x140);
    const uint32_t length = field<uint32_t>(engine, 0x150);
    if (!handler || !mapping || length == 0) {
        SYSLOG("vegauvd", "UVD clear rejected invalid firmware allocation");
        return false;
    }

    void *accelerator = field<void *>(handler, 0x10);
    if (!accelerator)
        return false;
    void *blitManager = field<void *>(accelerator, 0x1A58);
    void *atomicBlitter = field<void *>(accelerator, 0x1A60);
    void *eventMachine = field<void *>(accelerator, 0x380);
    void *task = field<void *>(accelerator, 0x1FF0);
    if (!blitManager || !atomicBlitter || !eventMachine || !task) {
        SYSLOG("vegauvd", "UVD clear rejected unavailable blitter");
        return false;
    }

    auto stamps = field<volatile uint32_t * const *>(eventMachine, 0x28);
    if (!stamps)
        return false;
    Event event {};
    for (auto &fence : event.fences)
        fence.channel = NoChannel;
    MemsetInfo info {};
    info.destination = field<uint64_t>(mapping, 0x20);
    info.length = length;
    if (info.destination == 0)
        return false;
    BlitOptions options {};
    options.event = &event;
    options.task = task;
    auto vtable = field<void **>(atomicBlitter, 0);
    if (!vtable || !vtable[0x158 / sizeof(void *)])
        return false;
    using DoMemset = uint32_t (*)(void *, MemsetInfo *, const BlitOptions *);
    auto doMemset = reinterpret_cast<DoMemset>(vtable[0x158 / sizeof(void *)]);
    const uint32_t result = doMemset(atomicBlitter, &info, &options);
    const uint32_t blitError = field<uint32_t>(atomicBlitter, 0xC);
    if (result != 0 || blitError != 0) {
        SYSLOG("vegauvd", "UVD clear submission failed result=%u blit=%u", result, blitError);
        return false;
    }

    uint64_t deadline {};
    clock_interval_to_deadline(ClearTimeoutMs, kMillisecondScale, &deadline);
    for (;;) {
        const auto status = fenceStatus(event, stamps);
        if (status == FenceStatus::Complete) {
            __sync_synchronize();
            return true;
        }
        if (status == FenceStatus::Invalid || mach_absolute_time() >= deadline) {
            SYSLOG("vegauvd", "UVD clear failed or timed out; aborting engine start");
            return false;
        }
        // Polling avoids finishEvent's recursive channel restart and mutex lock.
        IOSleep(1);
    }
}

} // namespace UvdRecovery
