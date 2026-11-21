#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdio>

static uint64_t testTime;
static uint64_t completeAt;
static volatile uint32_t completedStamp;
static void clock_interval_to_deadline(unsigned interval, unsigned, uint64_t *out) {
    *out = testTime + interval;
}
static uint64_t mach_absolute_time() { return testTime; }
static constexpr unsigned kMillisecondScale = 1;
static void IOSleep(unsigned milliseconds) {
    testTime += milliseconds;
    if (completeAt && testTime >= completeAt)
        completedStamp = 10;
}
#define SYSLOG(...) ((void)0)
#include "../CPUFriend/UvdRecovery.hpp"

using namespace UvdRecovery;

alignas(void *) static std::array<uint8_t, 0x320> engine;
alignas(void *) static std::array<uint8_t, 0x20> handler;
alignas(void *) static std::array<uint8_t, 0x30> mapping;
alignas(void *) static std::array<uint8_t, 0x2000> accelerator;
alignas(void *) static std::array<uint8_t, 0x30> eventMachine;
alignas(void *) static std::array<uint8_t, 0x18> blitter;
static void *blitterVtable[0x160 / sizeof(void *)];
static volatile uint32_t *stamps[HardwareChannels];
static unsigned calls;
static uint32_t channel;
static uint32_t submitResult;
static uint32_t submitError;

template <typename T>
static void put(void *object, size_t offset, T value) {
    std::memcpy(static_cast<uint8_t *>(object) + offset, &value, sizeof(value));
}

static uint32_t fakeMemset(void *object, MemsetInfo *info, const BlitOptions *options) {
    ++calls;
    assert(object == blitter.data());
    assert(info->destination == 0x1234000);
    assert(info->length == 4096 && info->value == 0);
    assert(options->task == engine.data());
    for (const auto &fence : options->event->fences)
        assert(fence.channel == NoChannel && fence.stamp == 0);
    options->event->fences[0] = {channel, 10};
    put<uint32_t>(blitter.data(), 0xC, submitError);
    return submitResult;
}

static void setup() {
    engine.fill(0);
    handler.fill(0);
    mapping.fill(0);
    accelerator.fill(0);
    eventMachine.fill(0);
    blitter.fill(0);
    std::memset(stamps, 0, sizeof(stamps));
    testTime = completeAt = calls = submitResult = submitError = 0;
    completedStamp = 10;
    channel = 5;
    stamps[5] = &completedStamp;
    blitterVtable[0x158 / sizeof(void *)] = reinterpret_cast<void *>(&fakeMemset);
    put<void *>(engine.data(), 0x20, handler.data());
    put<void *>(engine.data(), 0x140, mapping.data());
    put<uint32_t>(engine.data(), 0x150, 4096);
    put<void *>(handler.data(), 0x10, accelerator.data());
    put<uint64_t>(mapping.data(), 0x20, 0x1234000);
    put<void *>(accelerator.data(), 0x380, eventMachine.data());
    put<void *>(accelerator.data(), 0x1A58, handler.data());
    put<void *>(accelerator.data(), 0x1A60, blitter.data());
    put<void *>(accelerator.data(), 0x1FF0, engine.data());
    put<volatile uint32_t * const *>(eventMachine.data(), 0x28, stamps);
    put<void **>(blitter.data(), 0, blitterVtable);
}

int main() {
    setup();
    assert(clearFirmware(engine.data()) && calls == 1 && testTime == 0);
    setup();
    completedStamp = 9;
    completeAt = 3;
    assert(clearFirmware(engine.data()) && testTime == 3);
    setup();
    completedStamp = 9;
    assert(!clearFirmware(engine.data()) && testTime == ClearTimeoutMs);
    assert(completedStamp == 9); // A timeout must never fabricate GPU completion.
    setup();
    submitError = 3;
    assert(!clearFirmware(engine.data()) && testTime == 0);
    setup();
    submitResult = 1;
    assert(!clearFirmware(engine.data()));
    setup();
    channel = HardwareChannels;
    assert(!clearFirmware(engine.data()) && testTime == 0);
    setup();
    channel = NoChannel;
    assert(!clearFirmware(engine.data()) && testTime == 0);
    setup();
    stamps[5] = nullptr;
    assert(!clearFirmware(engine.data()));
    setup();
    put<uint32_t>(engine.data(), 0x150, 0);
    assert(!clearFirmware(engine.data()) && calls == 0);
    setup();
    put<void *>(engine.data(), 0x140, nullptr);
    assert(!clearFirmware(engine.data()) && calls == 0);
    setup();
    put<void *>(accelerator.data(), 0x1FF0, nullptr);
    assert(!clearFirmware(engine.data()) && calls == 0);

    setup();
    Event event {};
    for (auto &fence : event.fences)
        fence.channel = NoChannel;
    assert(fenceStatus(event, stamps) == FenceStatus::Invalid);
    event.fences[0] = {5, 1};
    completedStamp = 0xFFFFFFFE;
    assert(fenceStatus(event, stamps) == FenceStatus::Pending);
    completedStamp = 2;
    assert(fenceStatus(event, stamps) == FenceStatus::Complete);
    event.fences[1] = {HardwareChannels, 0};
    assert(fenceStatus(event, stamps) == FenceStatus::Invalid);
    assert(fenceStatus(event, nullptr) == FenceStatus::Invalid);
    std::puts("UVD recovery regression checks passed");
}
