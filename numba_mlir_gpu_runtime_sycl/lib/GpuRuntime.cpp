// SPDX-FileCopyrightText: 2023 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#ifdef _MSC_VER
#define _CRT_SECURE_NO_WARNINGS 1
#endif

#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <tuple>

#include "numba-mlir-gpu-runtime-sycl_export.h"

#include "Utils.hpp"

#include "GpuCommon.hpp"
#include "GpuModule.hpp"

#include <CL/sycl.hpp>

namespace {
static bool islogFunctionsEnabled() {
  static bool enable = []() -> bool {
    auto env = std::getenv("NUMBA_MLIR_LOG_GPU_RUNTIME_CALLS");
    return env && std::atoi(env) != 0;
  }();
  return enable;
}

struct FuncScope {
  FuncScope(const char *funcName)
      : name(funcName), enable(islogFunctionsEnabled()) {
    if (enable) {
      fprintf(stdout, "%s enter\n", name);
      fflush(stdout);
    }
  }
  FuncScope(const FuncScope &) = delete;
  ~FuncScope() {
    if (enable) {
      fprintf(stdout, "%s exit\n", name);
      fflush(stdout);
    }
  }

private:
  const char *name;
  bool enable;
};
} // namespace
#define LOG_FUNC() FuncScope _scope(__func__)

namespace {
static auto getDeviceSelector(std::string deviceName) {
  using Sel = sycl::ext::oneapi::filter_selector;
  return [selector = Sel(std::move(deviceName))](
             const sycl::device &dev) -> int { return selector(dev); };
}

template <typename T> static size_t countUntil(T *ptr, T &&elem) {
  assert(ptr);
  auto curr = ptr;
  while (*curr != elem) {
    ++curr;
  }
  return static_cast<size_t>(curr - ptr);
}

static auto countEvents(sycl::event **events) {
  assert(events);
  return static_cast<uint32_t>(
      countUntil(events, static_cast<sycl::event *>(nullptr)));
}

static void *checkAlloc(void *mem, const char *err) {
  if (!mem)
    throw std::runtime_error(err);

  return mem;
}

#define CHECK_ALLOC(mem, type)                                                 \
  checkAlloc(mem, "Failed to allocate " #type " memory")

struct EventStorage {
  sycl::event event;
  std::unique_ptr<EventStorage> next;
};
static_assert(offsetof(EventStorage, event) == 0, "Event must be first");

class Stream : public numba::GPUStreamInterface {
public:
  Stream(const char *devName) : deviceName(devName ? devName : "") {
    LOG_FUNC();
    queue = sycl::queue{sycl::device{getDeviceSelector(deviceName)}};
  }
  Stream(const Stream &) = delete;
  ~Stream() { LOG_FUNC(); }

  std::string_view getDeviceName() override { return deviceName; }

  sycl::queue *getQueue() override { return &queue; }

  void retain() { ++refcout; }

  void release() {
    if (--refcout == 0)
      delete this;
  }

  struct Releaser {
    Releaser(Stream *s) : stream(s) { assert(stream); }
    Releaser(const Releaser &) = delete;
    ~Releaser() { stream->release(); }

  private:
    Stream *stream;
  };

  GPUModule *loadModule(const void *data, size_t dataSize) {
    assert(data);
    return createGPUModule(queue, data, dataSize);
  }

  static auto destroyModule(GPUModule *module) {
    assert(module);
    destoyGPUModule(module);
  }

  static GPUKernel *getKernel(GPUModule *module, const char *name) {
    assert(module);
    assert(name);
    return getGPUKernel(module, name);
    ;
  }

  static void destroyKernel(GPUKernel *kernel) {
    assert(kernel);
    destroyGPUKernel(kernel);
  }

  sycl::event *launchKernel(GPUKernel *kernel, size_t gridX, size_t gridY,
                            size_t gridZ, size_t blockX, size_t blockY,
                            size_t blockZ, sycl::event **srcEvents,
                            numba::GPUParamDesc *params) {
    assert(kernel);
    auto eventsCount = countEvents(srcEvents);
    auto paramsCount = countUntil(
        params, numba::GPUParamDesc{nullptr, 0, numba::GpuParamType::null});

    auto evStorage = getEvent();
    assert(evStorage);

    auto globalRange =
        sycl::range<3>(blockZ * gridZ, blockY * gridY, blockX * gridX);
    auto localRange = ::sycl::range<3>(blockZ, blockY, blockX);
    auto ndRange = sycl::nd_range<3>(globalRange, localRange);
    auto syclKernel = getSYCLKernel(kernel);
    evStorage->event = queue.submit([&](sycl::handler &cgh) {
      for (decltype(eventsCount) i = 0; i < eventsCount; ++i) {
        auto event = srcEvents[i];
        assert(event);
        cgh.depends_on(*event);
      }

      for (decltype(paramsCount) i = 0; i < paramsCount; i++)
        setKernelArg(cgh, static_cast<uint32_t>(i), params[i]);

      cgh.parallel_for(ndRange, syclKernel);
    });

    return &(evStorage->event);
  }

  void waitEvent(sycl::event *event) {
    assert(event);
    event->wait();
  }

  void destroyEvent(sycl::event *event) {
    assert(event);
    auto storage = reinterpret_cast<EventStorage *>(event);
    returnEvent(storage);
  }

  std::tuple<void *, sycl::event *> allocBuffer(size_t size, size_t alignment,
                                                numba::GpuAllocType type,
                                                sycl::event **srcEvents) {
    // Alloc is always sync for now, synchronize
    auto eventsCount = countEvents(srcEvents);
    for (decltype(eventsCount) i = 0; i < eventsCount; ++i) {
      auto event = srcEvents[i];
      assert(event);
      event->wait();
    }

    auto evStorage = getEvent();

    auto mem = [&]() -> void * {
      void *ret = nullptr;
      if (type == numba::GpuAllocType::Device) {
        ret = CHECK_ALLOC(sycl::aligned_alloc_device(alignment, size, queue),
                          device);
      } else if (type == numba::GpuAllocType::Shared) {
        ret = CHECK_ALLOC(sycl::aligned_alloc_shared(alignment, size, queue),
                          shared);
      } else if (type == numba::GpuAllocType::Local) {
        // Local allocs are handled specially, do not allocate any pointer on
        // host side.
      } else {
        throw std::runtime_error("Invalid allocation type");
      }
      return ret;
    }();

    // Prolong gpu_runtime lifetime until all buffers are released (in case we
    // need to return allocated buffer from function).
    retain();
    return {mem, &(evStorage->event)};
  }

  void deallocBuffer(void *ptr) {
    if (ptr)
      sycl::free(ptr, queue);

    // We are incrementing runtime refcount in alloc.
    release();
  }

  void suggestBlockSize(GPUKernel *kernel, const uint32_t *gridSize,
                        uint32_t *blockSize, size_t numDims) {
    assert(kernel);
    suggestGPUBlockSize(kernel, gridSize, blockSize, numDims);
  }

private:
  std::atomic<unsigned> refcout = {1};
  sycl::queue queue;

  std::unique_ptr<EventStorage> events;
  std::string deviceName;

  EventStorage *getEvent() {
    EventStorage *ret = nullptr;
    if (!events) {
      ret = new EventStorage;
    } else {
      std::unique_ptr<EventStorage> ev = std::move(events);
      events = std::move(ev->next);
      ret = ev.release();
      ;
    }
    assert(ret);

    // Prolong runtime lifetime as long as there are outstanding events.
    retain();
    return ret;
  }

  void returnEvent(EventStorage *event) {
    assert(event);
    assert(!event->next);
    event->next = std::move(events);
    events.reset(event);

    // We are incrementing runtime refcount in getEvent.
    release();
  }

  template <numba::GpuParamType TypeVal, typename Type>
  static bool setKernelArgImpl(sycl::handler &cgh, uint32_t index,
                               const numba::GPUParamDesc &desc) {
    if (TypeVal == desc.type) {
      assert(desc.size == sizeof(Type));
      cgh.set_arg(index, *static_cast<const Type *>(desc.data));
      return true;
    }
    return false;
  }

  template <numba::GpuParamType TypeVal>
  static bool setKernelArgPtrImpl(sycl::handler &cgh, uint32_t index,
                                  const numba::GPUParamDesc &desc) {
    if (TypeVal == desc.type) {
      assert(desc.size == sizeof(void *));
      if (desc.data) {
        cgh.set_arg(index, *(static_cast<void *const *>(desc.data)));
      } else {
        // Local mem
        cgh.set_arg(index, sycl::local_accessor<char>(desc.size, cgh));
      }
      return true;
    }
    return false;
  }

  static void setKernelArg(sycl::handler &cgh, uint32_t index,
                           const numba::GPUParamDesc &desc) {
    using HandlerPtrT =
        bool (*)(sycl::handler &, uint32_t, const numba::GPUParamDesc &);
    const HandlerPtrT handlers[] = {
        &setKernelArgImpl<numba::GpuParamType::bool_, bool>,
        &setKernelArgImpl<numba::GpuParamType::int8, int8_t>,
        &setKernelArgImpl<numba::GpuParamType::int16, int16_t>,
        &setKernelArgImpl<numba::GpuParamType::int32, int32_t>,
        &setKernelArgImpl<numba::GpuParamType::int64, int64_t>,
        &setKernelArgImpl<numba::GpuParamType::float32, float>,
        &setKernelArgImpl<numba::GpuParamType::float64, double>,
        &setKernelArgPtrImpl<numba::GpuParamType::ptr>,
    };

    for (auto handler : handlers)
      if (handler(cgh, index, desc))
        return;

    fprintf(stdout, "Unhandled param type: %d\n", static_cast<int>(desc.type));
    fflush(stdout);
    abort();
  }
};

static Stream *toStream(void *stream) {
  assert(stream && "Invalid stream");
  return static_cast<Stream *>(stream);
}

} // namespace

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void *
gpuxStreamCreate(const char *deviceName) {
  LOG_FUNC();
  return catchAll([&]() { return new Stream(deviceName); });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void
gpuxStreamDestroy(void *stream) {
  LOG_FUNC();
  catchAll([&]() { toStream(stream)->release(); });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void *
gpuxModuleLoad(void *stream, const void *data, size_t dataSize) {
  LOG_FUNC();
  return catchAll(
      [&]() { return toStream(stream)->loadModule(data, dataSize); });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void
gpuxModuleDestroy(void *module) {
  LOG_FUNC();
  catchAll([&]() { Stream::destroyModule(static_cast<GPUModule *>(module)); });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void *
gpuxKernelGet(void *module, const char *name) {
  LOG_FUNC();
  return catchAll([&]() {
    return Stream::getKernel(static_cast<GPUModule *>(module), name);
  });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void
gpuxKernelDestroy(void *kernel) {
  LOG_FUNC();
  catchAll([&]() { Stream::destroyKernel(static_cast<GPUKernel *>(kernel)); });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void *
gpuxLaunchKernel(void *stream, void *kernel, size_t gridX, size_t gridY,
                 size_t gridZ, size_t blockX, size_t blockY, size_t blockZ,
                 void *events, void *params) {
  LOG_FUNC();
  return catchAll([&]() {
    return toStream(stream)->launchKernel(
        static_cast<GPUKernel *>(kernel), gridX, gridY, gridZ, blockX, blockY,
        blockZ, static_cast<sycl::event **>(events),
        static_cast<numba::GPUParamDesc *>(params));
  });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void gpuxWait(void *stream,
                                                            void *event) {
  LOG_FUNC();
  catchAll([&]() {
    toStream(stream)->waitEvent(static_cast<sycl::event *>(event));
  });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void
gpuxDestroyEvent(void *stream, void *event) {
  LOG_FUNC();
  catchAll([&]() {
    toStream(stream)->destroyEvent(static_cast<sycl::event *>(event));
  });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void
gpuxAlloc(void *stream, size_t size, size_t alignment, int type, void *events,
          numba::GPUAllocResult *ret) {
  LOG_FUNC();
  catchAll([&]() {
    auto res = toStream(stream)->allocBuffer(
        size, alignment, static_cast<numba::GpuAllocType>(type),
        static_cast<sycl::event **>(events));
    *ret = {std::get<0>(res), std::get<1>(res)};
  });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void gpuxDeAlloc(void *stream,
                                                               void *ptr) {
  LOG_FUNC();
  catchAll([&]() { toStream(stream)->deallocBuffer(ptr); });
}

extern "C" NUMBA_MLIR_GPU_RUNTIME_SYCL_EXPORT void
gpuxSuggestBlockSize(void *stream, void *kernel, const uint32_t *gridSize,
                     uint32_t *blockSize, size_t numDims) {
  LOG_FUNC();
  catchAll([&]() {
    toStream(stream)->suggestBlockSize(static_cast<GPUKernel *>(kernel),
                                       gridSize, blockSize, numDims);
  });
}
