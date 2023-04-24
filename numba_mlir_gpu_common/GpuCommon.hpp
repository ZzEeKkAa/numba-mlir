// SPDX-FileCopyrightText: 2023 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include <string_view>

namespace numba {

class GPUStreamInterface {
public:
  virtual ~GPUStreamInterface() = default;
  virtual std::string_view getDeviceName() = 0;
};

struct OffloadDeviceCapabilities {
  uint16_t spirvMajorVersion;
  uint16_t spirvMinorVersion;
  bool hasFP16;
  bool hasFP64;
};

enum class GpuAllocType { Device = 0, Shared = 1, Local = 2 };

enum class GpuParamType : int32_t {
  null = 0,
  int8,
  int16,
  int32,
  int64,
  float32,
  float64,
  ptr,
};

// Must be kept in sync with the compiler.
struct GPUParamDesc {
  const void *data;
  int32_t size;
  GpuParamType type;

  bool operator==(const GPUParamDesc &rhs) const {
    return data == rhs.data && size == rhs.size && type == rhs.type;
  }

  bool operator!=(const GPUParamDesc &rhs) const { return !(*this == rhs); }
};

typedef void (*MemInfoDtorFunction)(void *ptr, size_t size, void *info);
using MemInfoAllocFuncT = void *(*)(void *, size_t, MemInfoDtorFunction,
                                    void *);

struct GPUAllocResult {
  void *info;
  void *ptr;
  void *event;
};

} // namespace numba
