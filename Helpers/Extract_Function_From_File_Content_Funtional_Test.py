import unittest
import Extract_Function_From_File_Content_Helper as ExtractFunctionContent

helper = ExtractFunctionContent.ExtractFunctionFromFileContentHelper()

class ExtractFunctionTest(unittest.TestCase):
    def print_result(self, result):
        for item in result:
            ## Print only function signature:
            # print(f"\nFunction: {item[0].encode('utf-8', 'ignore').decode('utf-8')}\n")

            # Print function signature and function implementations:
            print(f"\nFunction: {item[0].encode('utf-8', 'ignore').decode('utf-8')}\n{item[1].encode('utf-8', 'ignore').decode('utf-8')}\n")

    ### Test function for 'extract_python_functions' ###
    def test_extract_python_functions(self):
        py_content_1 = '''
def functionA(arg_1,
    arg_2):   
    inside function A.
        inside function A.
    inside function A.

statement outside of the function.

def functionB(arg_1, arg_2):
    inside function B.

class A:
    def functionC(arg_1, arg_2):
        inside function C.

def functionD(arg_1, arg_2):
    inside function D.
'''

        result = helper.extract_python_functions(py_content_1)
        self.print_result(result)

        self.assertEqual(result[0][0], 'def functionA(arg_1, arg_2):')
        self.assertEqual(result[0][1], 'def functionA(arg_1,\n    arg_2):   \n    inside function A.\n        inside function A.\n    inside function A.')
        self.assertEqual(result[1][0], 'def functionB(arg_1, arg_2):')
        self.assertEqual(result[1][1], 'def functionB(arg_1, arg_2):\n    inside function B.')
        self.assertEqual(result[2][0], 'def functionC(arg_1, arg_2):')
        self.assertEqual(result[2][1], '    def functionC(arg_1, arg_2):\n        inside function C.')
        self.assertEqual(result[3][0], 'def functionD(arg_1, arg_2):')
        self.assertEqual(result[3][1], 'def functionD(arg_1, arg_2):\n    inside function D.')

    ### Test function for 'extract_c_functions' ###
    def test_extract_c_functions(self):
        c_content_1 = ''';
#include "config_components.h"

static void draw_digit(int digit, uint8_t *dst, ptrdiff_t dst_linesize, int segment_width)
{
    draw_rectangle(0, dst, dst_linesize, segment_width, 0, 0, 8, 13);
}

#define GRADIENT_SIZE (6 * 256)

void test_fill_picture(AVFilterContext *ctx, AVFrame *frame)
{
    TestSourceContext *test = ctx->priv;
    uint8_t *p, *p0;

    /* draw digits */
    seg_size = width / 80;
    if (seg_size >= 1 && height >= 13 * seg_size) {
        int64_t p10decimals = 1;
        double time = av_q2d(test->time_base) * test->nb_frame *
                      ff_exp10(test->nb_decimals);
        if (time >= INT_MAX)
            return;

        for (x = 0; x < test->nb_decimals; x++)
            p10decimals *= 10;

        second = av_rescale_rnd(test->nb_frame * test->time_base.num, p10decimals, test->time_base.den, AV_ROUND_ZERO);
        x = width - (width - seg_size * 64) / 2;
        y = (height - seg_size * 13) / 2;
        p = data + (x*3 + y * frame->linesize[0]);
        for (i = 0; i < 8; i++) {
            p -= 3 * 8 * seg_size;
            draw_digit(second % 10, p, frame->linesize[0], seg_size);
            second /= 10;
            if (second == 0)
                break;
        }
    }
}
#endif /* CONFIG_ZONEPLATE_FILTER */
'''
        
        c_content_2 = '''
#include <stdio.h>
#include <stdarg.h>

// Basic Function Declaration
int basicFunction(int a, int b) {
    return a + b;
}

// Function with No Parameters
void noParamFunction(void) {
    printf("No parameters\n");
}

// Function with Pointer Parameters
void pointerFunction(int* ptr) {
    *ptr = *ptr + 1;
}

// Overload function above
double pointerFunction(int* ptr, int a, int c) {
    *ptr = *ptr + 1;
}

// Function with Array Parameter
void arrayFunction(int arr[], int size) {
    for(int i = 0; i < size; i++) {
        printf("%d ", arr[i]);
    }
    printf("\\n");
}

// Function with Variable Arguments (using stdarg.h)
void varArgsFunction(const char* format, ...) {
    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
}

// Recursive Function
int recursiveFunction(int n) {
    if (n <= 1) return 1;
    return n * recursiveFunction(n - 1);
}

// Inline Function (C99 and later)
inline int inlineFunction(int a, int b) {
    return a * b;
}

// Function with Function Pointer as Parameter
void funcPointerFunction(void (*funcPtr)(void)) {
    funcPtr();
}

// A Simple Function to be used as a Function Pointer
void simpleFunction(void) {
    printf("Function Pointer Executed\\n");
}

// Main Function
int main() {
    printf("Test C Functions\\n");
    
    // Calling pointer function
    int val = 5;
    pointerFunction(&val);
    printf("Pointer Function Result: %d\\n", val);

    // Calling array function
    int arr[] = {1, 2, 3, 4, 5};
    arrayFunction(arr, 5);

    // Calling function with variable arguments
    varArgsFunction("Variable Arguments: %d %s\\n", 10, "test");

    // Calling function with function pointer
    funcPointerFunction(simpleFunction);

    return 0;
}
'''
        result = helper.extract_c_functions(c_content_1)
        self.print_result(result)

    ### Test function for 'extract_cpp_functions' ###
    def test_extract_cpp_functions(self):
        cpp_content_1 = '''
/* -*- Mode: C++; tab-width: 8; indent-tabs-mode: nil; c-basic-offset: 2 -*- */
/* vim: set ts=8 sts=2 et sw=2 tw=80: */
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */

#include "BaseProfiler.h"

#include "mozilla/Attributes.h"

#ifdef MOZ_GECKO_PROFILER
#  include "BaseProfileJSONWriter.h"
#  include "BaseProfilerMarkerPayload.h"
#  include "mozilla/BlocksRingBuffer.h"
#  include "mozilla/leb128iterator.h"
#  include "mozilla/ModuloBuffer.h"
#  include "mozilla/PowerOfTwo.h"
#  include "mozilla/ProfileBufferChunk.h"
#  include "mozilla/ProfileBufferChunkManagerSingle.h"
#  include "mozilla/ProfileBufferChunkManagerWithLocalLimit.h"
#  include "mozilla/ProfileBufferControlledChunkManager.h"
#  include "mozilla/ProfileChunkedBuffer.h"
#  include "mozilla/Vector.h"
#endif  // MOZ_GECKO_PROFILER

#if defined(_MSC_VER) || defined(__MINGW32__)
#  include <windows.h>
#  include <mmsystem.h>
#  include <process.h>
#else
#  include <errno.h>
#  include <string.h>
#  include <time.h>
#  include <unistd.h>
#endif

#include <algorithm>
#include <atomic>
#include <thread>
#include <type_traits>
#include <utility>

#ifdef MOZ_GECKO_PROFILER

MOZ_MAYBE_UNUSED static void SleepMilli(unsigned aMilliseconds) {
#if defined(_MSC_VER) || defined(__MINGW32__)
  Sleep(aMilliseconds);
#else
  struct timespec ts = {/* .tv_sec */ static_cast<time_t>(aMilliseconds / 1000),
                        /* ts.tv_nsec */ long(aMilliseconds % 1000) * 1000000};
  struct timespec tr = {0, 0};
  while (nanosleep(&ts, &tr)) {
    if (errno == EINTR) {
      ts = tr;
    } else {
      printf("nanosleep() -> %s\n", strerror(errno));
      exit(1);
    }
  }
#endif
}

using namespace mozilla;

void TestPowerOfTwoMask() {
  printf("TestPowerOfTwoMask...\n");

  static_assert(MakePowerOfTwoMask<uint32_t, 0>().MaskValue() == 0);
  constexpr PowerOfTwoMask<uint32_t> c0 = MakePowerOfTwoMask<uint32_t, 0>();
  MOZ_RELEASE_ASSERT(c0.MaskValue() == 0);

  static_assert(MakePowerOfTwoMask<uint32_t, 0xFFu>().MaskValue() == 0xFFu);
  constexpr PowerOfTwoMask<uint32_t> cFF =
      MakePowerOfTwoMask<uint32_t, 0xFFu>();
  MOZ_RELEASE_ASSERT(cFF.MaskValue() == 0xFFu);

  static_assert(MakePowerOfTwoMask<uint32_t, 0xFFFFFFFFu>().MaskValue() ==
                0xFFFFFFFFu);
  constexpr PowerOfTwoMask<uint32_t> cFFFFFFFF =
      MakePowerOfTwoMask<uint32_t, 0xFFFFFFFFu>();
  MOZ_RELEASE_ASSERT(cFFFFFFFF.MaskValue() == 0xFFFFFFFFu);

  struct TestDataU32 {
    uint32_t mInput;
    uint32_t mMask;
  };
  // clang-format off
  TestDataU32 tests[] = {
    { 0, 0 },
    { 1, 1 },
    { 2, 3 },
    { 3, 3 },
    { 4, 7 },
    { 5, 7 },
    { (1u << 31) - 1, (1u << 31) - 1 },
    { (1u << 31), uint32_t(-1) },
    { (1u << 31) + 1, uint32_t(-1) },
    { uint32_t(-1), uint32_t(-1) }
  };
  // clang-format on
  for (const TestDataU32& test : tests) {
    PowerOfTwoMask<uint32_t> p2m(test.mInput);
    MOZ_RELEASE_ASSERT(p2m.MaskValue() == test.mMask);
    for (const TestDataU32& inner : tests) {
      if (p2m.MaskValue() != uint32_t(-1)) {
        MOZ_RELEASE_ASSERT((inner.mInput % p2m) ==
                           (inner.mInput % (p2m.MaskValue() + 1)));
      }
      MOZ_RELEASE_ASSERT((inner.mInput & p2m) == (inner.mInput % p2m));
      MOZ_RELEASE_ASSERT((p2m & inner.mInput) == (inner.mInput & p2m));
    }
  }

  printf("TestPowerOfTwoMask done\n");
}

void TestPowerOfTwo() {
  printf("TestPowerOfTwo...\n");

  static_assert(MakePowerOfTwo<uint32_t, 1>().Value() == 1);
  constexpr PowerOfTwo<uint32_t> c1 = MakePowerOfTwo<uint32_t, 1>();
  MOZ_RELEASE_ASSERT(c1.Value() == 1);
  static_assert(MakePowerOfTwo<uint32_t, 1>().Mask().MaskValue() == 0);

  static_assert(MakePowerOfTwo<uint32_t, 128>().Value() == 128);
  constexpr PowerOfTwo<uint32_t> c128 = MakePowerOfTwo<uint32_t, 128>();
  MOZ_RELEASE_ASSERT(c128.Value() == 128);
  static_assert(MakePowerOfTwo<uint32_t, 128>().Mask().MaskValue() == 127);

  static_assert(MakePowerOfTwo<uint32_t, 0x80000000u>().Value() == 0x80000000u);
  constexpr PowerOfTwo<uint32_t> cMax = MakePowerOfTwo<uint32_t, 0x80000000u>();
  MOZ_RELEASE_ASSERT(cMax.Value() == 0x80000000u);
  static_assert(MakePowerOfTwo<uint32_t, 0x80000000u>().Mask().MaskValue() ==
                0x7FFFFFFFu);

  struct TestDataU32 {
    uint32_t mInput;
    uint32_t mValue;
    uint32_t mMask;
  };
  // clang-format off
  TestDataU32 tests[] = {
    { 0, 1, 0 },
    { 1, 1, 0 },
    { 2, 2, 1 },
    { 3, 4, 3 },
    { 4, 4, 3 },
    { 5, 8, 7 },
    { (1u << 31) - 1, (1u << 31), (1u << 31) - 1 },
    { (1u << 31), (1u << 31), (1u << 31) - 1 },
    { (1u << 31) + 1, (1u << 31), (1u << 31) - 1 },
    { uint32_t(-1), (1u << 31), (1u << 31) - 1 }
  };
  // clang-format on
  for (const TestDataU32& test : tests) {
    PowerOfTwo<uint32_t> p2(test.mInput);
    MOZ_RELEASE_ASSERT(p2.Value() == test.mValue);
    MOZ_RELEASE_ASSERT(p2.MaskValue() == test.mMask);
    PowerOfTwoMask<uint32_t> p2m = p2.Mask();
    MOZ_RELEASE_ASSERT(p2m.MaskValue() == test.mMask);
    for (const TestDataU32& inner : tests) {
      MOZ_RELEASE_ASSERT((inner.mInput % p2) == (inner.mInput % p2.Value()));
    }
  }

  printf("TestPowerOfTwo done\n");
}

void TestLEB128() {
  printf("TestLEB128...\n");

  MOZ_RELEASE_ASSERT(ULEB128MaxSize<uint8_t>() == 2);
  MOZ_RELEASE_ASSERT(ULEB128MaxSize<uint16_t>() == 3);
  MOZ_RELEASE_ASSERT(ULEB128MaxSize<uint32_t>() == 5);
  MOZ_RELEASE_ASSERT(ULEB128MaxSize<uint64_t>() == 10);

  struct TestDataU64 {
    uint64_t mValue;
    unsigned mSize;
    const char* mBytes;
  };
  // clang-format off
  TestDataU64 tests[] = {
    // Small numbers should keep their normal byte representation.
    {                  0u,  1, "\0" },
    {                  1u,  1, "\x01" },

    // 0111 1111 (127, or 0x7F) is the highest number that fits into a single
    // LEB128 byte. It gets encoded as 0111 1111, note the most significant bit
    // is off.
    {               0x7Fu,  1, "\x7F" },

    // Next number: 128, or 0x80.
    //   Original data representation:  1000 0000
    //     Broken up into groups of 7:         1  0000000
    // Padded with 0 (msB) or 1 (lsB):  00000001 10000000
    //            Byte representation:  0x01     0x80
    //            Little endian order:  -> 0x80 0x01
    {               0x80u,  2, "\x80\x01" },

    // Next: 129, or 0x81 (showing that we don't lose low bits.)
    //   Original data representation:  1000 0001
    //     Broken up into groups of 7:         1  0000001
    // Padded with 0 (msB) or 1 (lsB):  00000001 10000001
    //            Byte representation:  0x01     0x81
    //            Little endian order:  -> 0x81 0x01
    {               0x81u,  2, "\x81\x01" },

    // Highest 8-bit number: 255, or 0xFF.
    //   Original data representation:  1111 1111
    //     Broken up into groups of 7:         1  1111111
    // Padded with 0 (msB) or 1 (lsB):  00000001 11111111
    //            Byte representation:  0x01     0xFF
    //            Little endian order:  -> 0xFF 0x01
    {               0xFFu,  2, "\xFF\x01" },

    // Next: 256, or 0x100.
    //   Original data representation:  1 0000 0000
    //     Broken up into groups of 7:        10  0000000
    // Padded with 0 (msB) or 1 (lsB):  00000010 10000000
    //            Byte representation:  0x10     0x80
    //            Little endian order:  -> 0x80 0x02
    {              0x100u,  2, "\x80\x02" },

    // Highest 32-bit number: 0xFFFFFFFF (8 bytes, all bits set).
    // Original: 1111 1111 1111 1111 1111 1111 1111 1111
    // Groups:     1111  1111111  1111111  1111111  1111111
    // Padded: 00001111 11111111 11111111 11111111 11111111
    // Bytes:  0x0F     0xFF     0xFF     0xFF     0xFF
    // Little Endian: -> 0xFF 0xFF 0xFF 0xFF 0x0F
    {         0xFFFFFFFFu,  5, "\xFF\xFF\xFF\xFF\x0F" },

    // Highest 64-bit number: 0xFFFFFFFFFFFFFFFF (16 bytes, all bits set).
    // 64 bits, that's 9 groups of 7 bits, plus 1 (most significant) bit.
    { 0xFFFFFFFFFFFFFFFFu, 10, "\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x01" }
  };
  // clang-format on

  for (const TestDataU64& test : tests) {
    MOZ_RELEASE_ASSERT(ULEB128Size(test.mValue) == test.mSize);
    // Prepare a buffer that can accomodate the largest-possible LEB128.
    uint8_t buffer[ULEB128MaxSize<uint64_t>()];
    // Use a pointer into the buffer as iterator.
    uint8_t* p = buffer;
    // And write the LEB128.
    WriteULEB128(test.mValue, p);
    // Pointer (iterator) should have advanced just past the expected LEB128
    // size.
    MOZ_RELEASE_ASSERT(p == buffer + test.mSize);
    // Check expected bytes.
    for (unsigned i = 0; i < test.mSize; ++i) {
      MOZ_RELEASE_ASSERT(buffer[i] == uint8_t(test.mBytes[i]));
    }

    // Move pointer (iterator) back to start of buffer.
    p = buffer;
    // And read the LEB128 we wrote above.
    uint64_t read = ReadULEB128<uint64_t>(p);
    // Pointer (iterator) should have also advanced just past the expected
    // LEB128 size.
    MOZ_RELEASE_ASSERT(p == buffer + test.mSize);
    // And check the read value.
    MOZ_RELEASE_ASSERT(read == test.mValue);

    // Testing ULEB128 reader.
    ULEB128Reader<uint64_t> reader;
    MOZ_RELEASE_ASSERT(!reader.IsComplete());
    // Move pointer back to start of buffer.
    p = buffer;
    for (;;) {
      // Read a byte and feed it to the reader.
      if (reader.FeedByteIsComplete(*p++)) {
        break;
      }
      // Not complete yet, we shouldn't have reached the end pointer.
      MOZ_RELEASE_ASSERT(!reader.IsComplete());
      MOZ_RELEASE_ASSERT(p < buffer + test.mSize);
    }
    MOZ_RELEASE_ASSERT(reader.IsComplete());
    // Pointer should have advanced just past the expected LEB128 size.
    MOZ_RELEASE_ASSERT(p == buffer + test.mSize);
    // And check the read value.
    MOZ_RELEASE_ASSERT(reader.Value() == test.mValue);

    // And again after a Reset.
    reader.Reset();
    MOZ_RELEASE_ASSERT(!reader.IsComplete());
    p = buffer;
    for (;;) {
      if (reader.FeedByteIsComplete(*p++)) {
        break;
      }
      MOZ_RELEASE_ASSERT(!reader.IsComplete());
      MOZ_RELEASE_ASSERT(p < buffer + test.mSize);
    }
    MOZ_RELEASE_ASSERT(reader.IsComplete());
    MOZ_RELEASE_ASSERT(p == buffer + test.mSize);
    MOZ_RELEASE_ASSERT(reader.Value() == test.mValue);
  }

  printf("TestLEB128 done\n");
}

template <uint8_t byte, uint8_t... tail>
constexpr bool TestConstexprULEB128Reader(ULEB128Reader<uint64_t>& aReader) {
  if (aReader.IsComplete()) {
    return false;
  }
  const bool isComplete = aReader.FeedByteIsComplete(byte);
  if (aReader.IsComplete() != isComplete) {
    return false;
  }
  if constexpr (sizeof...(tail) == 0) {
    return isComplete;
  } else {
    if (isComplete) {
      return false;
    }
    return TestConstexprULEB128Reader<tail...>(aReader);
  }
}

template <uint64_t expected, uint8_t... bytes>
constexpr bool TestConstexprULEB128Reader() {
  ULEB128Reader<uint64_t> reader;
  if (!TestConstexprULEB128Reader<bytes...>(reader)) {
    return false;
  }
  if (!reader.IsComplete()) {
    return false;
  }
  if (reader.Value() != expected) {
    return false;
  }

  reader.Reset();
  if (!TestConstexprULEB128Reader<bytes...>(reader)) {
    return false;
  }
  if (!reader.IsComplete()) {
    return false;
  }
  if (reader.Value() != expected) {
    return false;
  }

  return true;
}

static_assert(TestConstexprULEB128Reader<0x0u, 0x0u>());
static_assert(!TestConstexprULEB128Reader<0x0u, 0x0u, 0x0u>());
static_assert(TestConstexprULEB128Reader<0x1u, 0x1u>());
static_assert(TestConstexprULEB128Reader<0x7Fu, 0x7Fu>());
static_assert(TestConstexprULEB128Reader<0x80u, 0x80u, 0x01u>());
static_assert(!TestConstexprULEB128Reader<0x80u, 0x80u>());
static_assert(!TestConstexprULEB128Reader<0x80u, 0x01u>());
static_assert(TestConstexprULEB128Reader<0x81u, 0x81u, 0x01u>());
static_assert(TestConstexprULEB128Reader<0xFFu, 0xFFu, 0x01u>());
static_assert(TestConstexprULEB128Reader<0x100u, 0x80u, 0x02u>());
static_assert(TestConstexprULEB128Reader<0xFFFFFFFFu, 0xFFu, 0xFFu, 0xFFu,
                                         0xFFu, 0x0Fu>());
static_assert(
    !TestConstexprULEB128Reader<0xFFFFFFFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu>());
static_assert(!TestConstexprULEB128Reader<0xFFFFFFFFu, 0xFFu, 0xFFu, 0xFFu,
                                          0xFFu, 0xFFu, 0x0Fu>());
static_assert(
    TestConstexprULEB128Reader<0xFFFFFFFFFFFFFFFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu,
                               0xFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu, 0x01u>());
static_assert(
    !TestConstexprULEB128Reader<0xFFFFFFFFFFFFFFFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu,
                                0xFFu, 0xFFu, 0xFFu, 0xFFu, 0xFFu>());

static void TestChunk() {
  printf("TestChunk...\n");

  static_assert(!std::is_default_constructible_v<ProfileBufferChunk>,
                "ProfileBufferChunk should not be default-constructible");
  static_assert(
      !std::is_constructible_v<ProfileBufferChunk, ProfileBufferChunk::Length>,
      "ProfileBufferChunk should not be constructible from Length");

  static_assert(
      sizeof(ProfileBufferChunk::Header) ==
          sizeof(ProfileBufferChunk::Header::mOffsetFirstBlock) +
              sizeof(ProfileBufferChunk::Header::mOffsetPastLastBlock) +
              sizeof(ProfileBufferChunk::Header::mDoneTimeStamp) +
              sizeof(ProfileBufferChunk::Header::mBufferBytes) +
              sizeof(ProfileBufferChunk::Header::mBlockCount) +
              sizeof(ProfileBufferChunk::Header::mRangeStart) +
              sizeof(ProfileBufferChunk::Header::mProcessId) +
              sizeof(ProfileBufferChunk::Header::mPADDING),
      "ProfileBufferChunk::Header may have unwanted padding, please review");
  // Note: The above static_assert is an attempt at keeping
  // ProfileBufferChunk::Header tightly packed, but some changes could make this
  // impossible to achieve (most probably due to alignment) -- Just do your
  // best!

  constexpr ProfileBufferChunk::Length TestLen = 1000;

  // Basic allocations of different sizes.
  for (ProfileBufferChunk::Length len = 0; len <= TestLen; ++len) {
    auto chunk = ProfileBufferChunk::Create(len);
    static_assert(
        std::is_same_v<decltype(chunk), UniquePtr<ProfileBufferChunk>>,
        "ProfileBufferChunk::Create() should return a "
        "UniquePtr<ProfileBufferChunk>");
    MOZ_RELEASE_ASSERT(!!chunk, "OOM!?");
    MOZ_RELEASE_ASSERT(chunk->BufferBytes() >= len);
    MOZ_RELEASE_ASSERT(chunk->ChunkBytes() >=
                       len + ProfileBufferChunk::SizeofChunkMetadata());
    MOZ_RELEASE_ASSERT(chunk->RemainingBytes() == chunk->BufferBytes());
    MOZ_RELEASE_ASSERT(chunk->OffsetFirstBlock() == 0);
    MOZ_RELEASE_ASSERT(chunk->OffsetPastLastBlock() == 0);
    MOZ_RELEASE_ASSERT(chunk->BlockCount() == 0);
    MOZ_RELEASE_ASSERT(chunk->ProcessId() == 0);
    MOZ_RELEASE_ASSERT(chunk->RangeStart() == 0);
    MOZ_RELEASE_ASSERT(chunk->BufferSpan().LengthBytes() ==
                       chunk->BufferBytes());
    MOZ_RELEASE_ASSERT(!chunk->GetNext());
    MOZ_RELEASE_ASSERT(!chunk->ReleaseNext());
    MOZ_RELEASE_ASSERT(chunk->Last() == chunk.get());
  }

  // Allocate the main test Chunk.
  auto chunkA = ProfileBufferChunk::Create(TestLen);
  MOZ_RELEASE_ASSERT(!!chunkA, "OOM!?");
  MOZ_RELEASE_ASSERT(chunkA->BufferBytes() >= TestLen);
  MOZ_RELEASE_ASSERT(chunkA->ChunkBytes() >=
                     TestLen + ProfileBufferChunk::SizeofChunkMetadata());
  MOZ_RELEASE_ASSERT(!chunkA->GetNext());
  MOZ_RELEASE_ASSERT(!chunkA->ReleaseNext());

  constexpr ProfileBufferIndex chunkARangeStart = 12345;
  chunkA->SetRangeStart(chunkARangeStart);
  MOZ_RELEASE_ASSERT(chunkA->RangeStart() == chunkARangeStart);

  // Get a read-only span over its buffer.
  auto bufferA = chunkA->BufferSpan();
  static_assert(
      std::is_same_v<decltype(bufferA), Span<const ProfileBufferChunk::Byte>>,
      "BufferSpan() should return a Span<const Byte>");
  MOZ_RELEASE_ASSERT(bufferA.LengthBytes() == chunkA->BufferBytes());

  // Add the initial tail block.
  constexpr ProfileBufferChunk::Length initTailLen = 10;
  auto initTail = chunkA->ReserveInitialBlockAsTail(initTailLen);
  static_assert(
      std::is_same_v<decltype(initTail), Span<ProfileBufferChunk::Byte>>,
      "ReserveInitialBlockAsTail() should return a Span<Byte>");
  MOZ_RELEASE_ASSERT(initTail.LengthBytes() == initTailLen);
  MOZ_RELEASE_ASSERT(initTail.Elements() == bufferA.Elements());
  MOZ_RELEASE_ASSERT(chunkA->OffsetFirstBlock() == initTailLen);
  MOZ_RELEASE_ASSERT(chunkA->OffsetPastLastBlock() == initTailLen);

  // Add the first complete block.
  constexpr ProfileBufferChunk::Length block1Len = 20;
  auto block1 = chunkA->ReserveBlock(block1Len);
  static_assert(
      std::is_same_v<decltype(block1), ProfileBufferChunk::ReserveReturn>,
      "ReserveBlock() should return a ReserveReturn");
  MOZ_RELEASE_ASSERT(block1.mBlockRangeIndex.ConvertToProfileBufferIndex() ==
                     chunkARangeStart + initTailLen);
  MOZ_RELEASE_ASSERT(block1.mSpan.LengthBytes() == block1Len);
  MOZ_RELEASE_ASSERT(block1.mSpan.Elements() ==
                     bufferA.Elements() + initTailLen);
  MOZ_RELEASE_ASSERT(chunkA->OffsetFirstBlock() == initTailLen);
  MOZ_RELEASE_ASSERT(chunkA->OffsetPastLastBlock() == initTailLen + block1Len);
  MOZ_RELEASE_ASSERT(chunkA->RemainingBytes() != 0);

  // Add another block to over-fill the ProfileBufferChunk.
  const ProfileBufferChunk::Length remaining =
      chunkA->BufferBytes() - (initTailLen + block1Len);
  constexpr ProfileBufferChunk::Length overfill = 30;
  const ProfileBufferChunk::Length block2Len = remaining + overfill;
  ProfileBufferChunk::ReserveReturn block2 = chunkA->ReserveBlock(block2Len);
  MOZ_RELEASE_ASSERT(block2.mBlockRangeIndex.ConvertToProfileBufferIndex() ==
                     chunkARangeStart + initTailLen + block1Len);
  MOZ_RELEASE_ASSERT(block2.mSpan.LengthBytes() == remaining);
  MOZ_RELEASE_ASSERT(block2.mSpan.Elements() ==
                     bufferA.Elements() + initTailLen + block1Len);
  MOZ_RELEASE_ASSERT(chunkA->OffsetFirstBlock() == initTailLen);
  MOZ_RELEASE_ASSERT(chunkA->OffsetPastLastBlock() == chunkA->BufferBytes());
  MOZ_RELEASE_ASSERT(chunkA->RemainingBytes() == 0);

  // Block must be marked "done" before it can be recycled.
  chunkA->MarkDone();

  // It must be marked "recycled" before data can be added to it again.
  chunkA->MarkRecycled();

  // Add an empty initial tail block.
  Span<ProfileBufferChunk::Byte> initTail2 =
      chunkA->ReserveInitialBlockAsTail(0);
  MOZ_RELEASE_ASSERT(initTail2.LengthBytes() == 0);
  MOZ_RELEASE_ASSERT(initTail2.Elements() == bufferA.Elements());
  MOZ_RELEASE_ASSERT(chunkA->OffsetFirstBlock() == 0);
  MOZ_RELEASE_ASSERT(chunkA->OffsetPastLastBlock() == 0);

  // Block must be marked "done" before it can be destroyed.
  chunkA->MarkDone();

  chunkA->SetProcessId(123);
  MOZ_RELEASE_ASSERT(chunkA->ProcessId() == 123);

  printf("TestChunk done\n");
}

static void TestChunkManagerSingle() {
  printf("TestChunkManagerSingle...\n");

  // Construct a ProfileBufferChunkManagerSingle for one chunk of size >=1000.
  constexpr ProfileBufferChunk::Length ChunkMinBufferBytes = 1000;
  ProfileBufferChunkManagerSingle cms{ChunkMinBufferBytes};

  // Reference to base class, to exercize virtual methods.
  ProfileBufferChunkManager& cm = cms;

#  ifdef DEBUG
  const char* chunkManagerRegisterer = "TestChunkManagerSingle";
  cm.RegisteredWith(chunkManagerRegisterer);
#  endif  // DEBUG

  const auto maxTotalSize = cm.MaxTotalSize();
  MOZ_RELEASE_ASSERT(maxTotalSize >= ChunkMinBufferBytes);

  cm.SetChunkDestroyedCallback([](const ProfileBufferChunk&) {
    MOZ_RELEASE_ASSERT(
        false,
        "ProfileBufferChunkManagerSingle should never destroy its one chunk");
  });

  UniquePtr<ProfileBufferChunk> extantReleasedChunks =
      cm.GetExtantReleasedChunks();
  MOZ_RELEASE_ASSERT(!extantReleasedChunks, "Unexpected released chunk(s)");

  // First request.
  UniquePtr<ProfileBufferChunk> chunk = cm.GetChunk();
  MOZ_RELEASE_ASSERT(!!chunk, "First chunk request should always work");
  MOZ_RELEASE_ASSERT(chunk->BufferBytes() >= ChunkMinBufferBytes,
                     "Unexpected chunk size");
  MOZ_RELEASE_ASSERT(!chunk->GetNext(), "There should only be one chunk");

  // Keep address, for later checks.
  const uintptr_t chunkAddress = reinterpret_cast<uintptr_t>(chunk.get());

  extantReleasedChunks = cm.GetExtantReleasedChunks();
  MOZ_RELEASE_ASSERT(!extantReleasedChunks, "Unexpected released chunk(s)");

  // Second request.
  MOZ_RELEASE_ASSERT(!cm.GetChunk(), "Second chunk request should always fail");

  extantReleasedChunks = cm.GetExtantReleasedChunks();
  MOZ_RELEASE_ASSERT(!extantReleasedChunks, "Unexpected released chunk(s)");

  // Add some data to the chunk (to verify recycling later on).
  MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetFirstBlock == 0);
  MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetPastLastBlock == 0);
  MOZ_RELEASE_ASSERT(chunk->RangeStart() == 0);
  chunk->SetRangeStart(100);
  MOZ_RELEASE_ASSERT(chunk->RangeStart() == 100);
  Unused << chunk->ReserveInitialBlockAsTail(1);
  Unused << chunk->ReserveBlock(2);
  MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetFirstBlock == 1);
  MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetPastLastBlock == 1 + 2);

  // Release the first chunk.
  chunk->MarkDone();
  cm.ReleaseChunks(std::move(chunk));
  MOZ_RELEASE_ASSERT(!chunk, "chunk UniquePtr should have been moved-from");

  // Request after release.
  MOZ_RELEASE_ASSERT(!cm.GetChunk(),
                     "Chunk request after release should also fail");

  // Check released chunk.
  extantReleasedChunks = cm.GetExtantReleasedChunks();
  MOZ_RELEASE_ASSERT(!!extantReleasedChunks,
                     "Could not retrieve released chunk");
  MOZ_RELEASE_ASSERT(!extantReleasedChunks->GetNext(),
                     "There should only be one released chunk");
  MOZ_RELEASE_ASSERT(
      reinterpret_cast<uintptr_t>(extantReleasedChunks.get()) == chunkAddress,
      "Released chunk should be first requested one");

  MOZ_RELEASE_ASSERT(!cm.GetExtantReleasedChunks(),
                     "Unexpected extra released chunk(s)");

  // Another request after release.
  MOZ_RELEASE_ASSERT(!cm.GetChunk(),
                     "Chunk request after release should also fail");

  MOZ_RELEASE_ASSERT(
      cm.MaxTotalSize() == maxTotalSize,
      "MaxTotalSize() should not change after requests&releases");

  // Reset the chunk manager. (Single-only non-virtual function.)
  cms.Reset(std::move(extantReleasedChunks));
  MOZ_RELEASE_ASSERT(!extantReleasedChunks,
                     "Released chunk UniquePtr should have been moved-from");

  MOZ_RELEASE_ASSERT(
      cm.MaxTotalSize() == maxTotalSize,
      "MaxTotalSize() should not change when resetting with the same chunk");

  // 2nd round, first request. Theoretically async, but this implementation just
  // immediately runs the callback.
  bool ran = false;
  cm.RequestChunk([&](UniquePtr<ProfileBufferChunk> aChunk) {
    ran = true;
    MOZ_RELEASE_ASSERT(!!aChunk);
    chunk = std::move(aChunk);
  });
  MOZ_RELEASE_ASSERT(ran, "RequestChunk callback not called immediately");
  ran = false;
  cm.FulfillChunkRequests();
  MOZ_RELEASE_ASSERT(!ran, "FulfillChunkRequests should not have any effects");
  MOZ_RELEASE_ASSERT(!!chunk, "First chunk request should always work");
  MOZ_RELEASE_ASSERT(chunk->BufferBytes() >= ChunkMinBufferBytes,
                     "Unexpected chunk size");
  MOZ_RELEASE_ASSERT(!chunk->GetNext(), "There should only be one chunk");
  MOZ_RELEASE_ASSERT(reinterpret_cast<uintptr_t>(chunk.get()) == chunkAddress,
                     "Requested chunk should be first requested one");
  // Verify that chunk is empty and usable.
  MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetFirstBlock == 0);
  MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetPastLastBlock == 0);
  MOZ_RELEASE_ASSERT(chunk->RangeStart() == 0);
  chunk->SetRangeStart(200);
  MOZ_RELEASE_ASSERT(chunk->RangeStart() == 200);
  Unused << chunk->ReserveInitialBlockAsTail(3);
  Unused << chunk->ReserveBlock(4);
  MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetFirstBlock == 3);
  MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetPastLastBlock == 3 + 4);

  // Second request.
  ran = false;
  cm.RequestChunk([&](UniquePtr<ProfileBufferChunk> aChunk) {
    ran = true;
    MOZ_RELEASE_ASSERT(!aChunk, "Second chunk request should always fail");
  });
  MOZ_RELEASE_ASSERT(ran, "RequestChunk callback not called");

  // This one does nothing.
  cm.ForgetUnreleasedChunks();

  // Don't forget to mark chunk "Done" before letting it die.
  chunk->MarkDone();
  chunk = nullptr;

  // Create a tiny chunk and reset the chunk manager with it.
  chunk = ProfileBufferChunk::Create(1);
  MOZ_RELEASE_ASSERT(!!chunk);
  auto tinyChunkSize = chunk->BufferBytes();
  MOZ_RELEASE_ASSERT(tinyChunkSize >= 1);
  MOZ_RELEASE_ASSERT(tinyChunkSize < ChunkMinBufferBytes);
  MOZ_RELEASE_ASSERT(chunk->RangeStart() == 0);
  chunk->SetRangeStart(300);
  MOZ_RELEASE_ASSERT(chunk->RangeStart() == 300);
  cms.Reset(std::move(chunk));
  MOZ_RELEASE_ASSERT(!chunk, "chunk UniquePtr should have been moved-from");
  MOZ_RELEASE_ASSERT(cm.MaxTotalSize() == tinyChunkSize,
                     "MaxTotalSize() should match the new chunk size");
  chunk = cm.GetChunk();
  MOZ_RELEASE_ASSERT(chunk->RangeStart() == 0, "Got non-recycled chunk");

  // Enough testing! Clean-up.
  Unused << chunk->ReserveInitialBlockAsTail(0);
  chunk->MarkDone();
  cm.ForgetUnreleasedChunks();

#  ifdef DEBUG
  cm.DeregisteredFrom(chunkManagerRegisterer);
#  endif  // DEBUG

  printf("TestChunkManagerSingle done\n");
}

static void TestChunkManagerWithLocalLimit() {
  printf("TestChunkManagerWithLocalLimit...\n");

  // Construct a ProfileBufferChunkManagerWithLocalLimit with chunk of minimum
  // size >=100, up to 1000 bytes.
  constexpr ProfileBufferChunk::Length MaxTotalBytes = 1000;
  constexpr ProfileBufferChunk::Length ChunkMinBufferBytes = 100;
  ProfileBufferChunkManagerWithLocalLimit cmll{MaxTotalBytes,
                                               ChunkMinBufferBytes};

  // Reference to base class, to exercize virtual methods.
  ProfileBufferChunkManager& cm = cmll;

#  ifdef DEBUG
  const char* chunkManagerRegisterer = "TestChunkManagerWithLocalLimit";
  cm.RegisteredWith(chunkManagerRegisterer);
#  endif  // DEBUG

  MOZ_RELEASE_ASSERT(cm.MaxTotalSize() == MaxTotalBytes,
                     "Max total size should be exactly as given");

  unsigned destroyedChunks = 0;
  unsigned destroyedBytes = 0;
  cm.SetChunkDestroyedCallback([&](const ProfileBufferChunk& aChunks) {
    for (const ProfileBufferChunk* chunk = &aChunks; chunk;
         chunk = chunk->GetNext()) {
      destroyedChunks += 1;
      destroyedBytes += chunk->BufferBytes();
    }
  });

  UniquePtr<ProfileBufferChunk> extantReleasedChunks =
      cm.GetExtantReleasedChunks();
  MOZ_RELEASE_ASSERT(!extantReleasedChunks, "Unexpected released chunk(s)");

  // First request.
  UniquePtr<ProfileBufferChunk> chunk = cm.GetChunk();
  MOZ_RELEASE_ASSERT(!!chunk,
                     "First chunk immediate request should always work");
  const auto chunkActualBufferBytes = chunk->BufferBytes();
  MOZ_RELEASE_ASSERT(chunkActualBufferBytes >= ChunkMinBufferBytes,
                     "Unexpected chunk size");
  MOZ_RELEASE_ASSERT(!chunk->GetNext(), "There should only be one chunk");

  // Keep address, for later checks.
  const uintptr_t chunk1Address = reinterpret_cast<uintptr_t>(chunk.get());

  extantReleasedChunks = cm.GetExtantReleasedChunks();
  MOZ_RELEASE_ASSERT(!extantReleasedChunks, "Unexpected released chunk(s)");

  // For this test, we need to be able to get at least 2 chunks without hitting
  // the limit. (If this failed, it wouldn't necessary be a problem with
  // ProfileBufferChunkManagerWithLocalLimit, fiddle with constants at the top
  // of this test.)
  MOZ_RELEASE_ASSERT(chunkActualBufferBytes < 2 * MaxTotalBytes);

  unsigned chunk1ReuseCount = 0;

  // We will do enough loops to go through the maximum size a number of times.
  const unsigned Rollovers = 3;
  const unsigned Loops = Rollovers * MaxTotalBytes / chunkActualBufferBytes;
  for (unsigned i = 0; i < Loops; ++i) {
    // Add some data to the chunk.
    MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetFirstBlock == 0);
    MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetPastLastBlock == 0);
    MOZ_RELEASE_ASSERT(chunk->RangeStart() == 0);
    const ProfileBufferIndex index = 1 + i * chunkActualBufferBytes;
    chunk->SetRangeStart(index);
    MOZ_RELEASE_ASSERT(chunk->RangeStart() == index);
    Unused << chunk->ReserveInitialBlockAsTail(1);
    Unused << chunk->ReserveBlock(2);
    MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetFirstBlock == 1);
    MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mOffsetPastLastBlock == 1 + 2);

    // Request a new chunk.
    bool ran = false;
    UniquePtr<ProfileBufferChunk> newChunk;
    cm.RequestChunk([&](UniquePtr<ProfileBufferChunk> aChunk) {
      ran = true;
      newChunk = std::move(aChunk);
    });
    MOZ_RELEASE_ASSERT(
        !ran, "RequestChunk should not immediately fulfill the request");
    cm.FulfillChunkRequests();
    MOZ_RELEASE_ASSERT(ran, "FulfillChunkRequests should invoke the callback");
    MOZ_RELEASE_ASSERT(!!newChunk, "Chunk request should always work");
    MOZ_RELEASE_ASSERT(newChunk->BufferBytes() == chunkActualBufferBytes,
                       "Unexpected chunk size");
    MOZ_RELEASE_ASSERT(!newChunk->GetNext(), "There should only be one chunk");

    // Mark previous chunk done and release it.
    chunk->MarkDone();
    cm.ReleaseChunks(std::move(chunk));

    // And cycle to the new chunk.
    chunk = std::move(newChunk);

    if (reinterpret_cast<uintptr_t>(chunk.get()) == chunk1Address) {
      ++chunk1ReuseCount;
    }
  }

  // Expect all rollovers except 1 to destroy chunks.
  MOZ_RELEASE_ASSERT(destroyedChunks >= (Rollovers - 1) * MaxTotalBytes /
                                            chunkActualBufferBytes,
                     "Not enough destroyed chunks");
  MOZ_RELEASE_ASSERT(destroyedBytes == destroyedChunks * chunkActualBufferBytes,
                     "Mismatched destroyed chunks and bytes");
  MOZ_RELEASE_ASSERT(chunk1ReuseCount >= (Rollovers - 1),
                     "Not enough reuse of the first chunks");

  // Check that chunk manager is reentrant from request callback.
  bool ran = false;
  bool ranInner = false;
  UniquePtr<ProfileBufferChunk> newChunk;
  cm.RequestChunk([&](UniquePtr<ProfileBufferChunk> aChunk) {
    ran = true;
    MOZ_RELEASE_ASSERT(!!aChunk, "Chunk request should always work");
    Unused << aChunk->ReserveInitialBlockAsTail(0);
    aChunk->MarkDone();
    UniquePtr<ProfileBufferChunk> anotherChunk = cm.GetChunk();
    MOZ_RELEASE_ASSERT(!!anotherChunk);
    Unused << anotherChunk->ReserveInitialBlockAsTail(0);
    anotherChunk->MarkDone();
    cm.RequestChunk([&](UniquePtr<ProfileBufferChunk> aChunk) {
      ranInner = true;
      MOZ_RELEASE_ASSERT(!!aChunk, "Chunk request should always work");
      Unused << aChunk->ReserveInitialBlockAsTail(0);
      aChunk->MarkDone();
    });
    MOZ_RELEASE_ASSERT(
        !ranInner, "RequestChunk should not immediately fulfill the request");
  });
  MOZ_RELEASE_ASSERT(!ran,
                     "RequestChunk should not immediately fulfill the request");
  MOZ_RELEASE_ASSERT(
      !ranInner,
      "RequestChunk should not immediately fulfill the inner request");
  cm.FulfillChunkRequests();
  MOZ_RELEASE_ASSERT(ran, "FulfillChunkRequests should invoke the callback");
  MOZ_RELEASE_ASSERT(!ranInner,
                     "FulfillChunkRequests should not immediately fulfill "
                     "the inner request");
  cm.FulfillChunkRequests();
  MOZ_RELEASE_ASSERT(
      ran, "2nd FulfillChunkRequests should invoke the inner request callback");

  // Enough testing! Clean-up.
  Unused << chunk->ReserveInitialBlockAsTail(0);
  chunk->MarkDone();
  cm.ForgetUnreleasedChunks();

#  ifdef DEBUG
  cm.DeregisteredFrom(chunkManagerRegisterer);
#  endif  // DEBUG

  printf("TestChunkManagerWithLocalLimit done\n");
}

static bool IsSameMetadata(
    const ProfileBufferControlledChunkManager::ChunkMetadata& a1,
    const ProfileBufferControlledChunkManager::ChunkMetadata& a2) {
  return a1.mDoneTimeStamp == a2.mDoneTimeStamp &&
         a1.mBufferBytes == a2.mBufferBytes;
};

static bool IsSameUpdate(
    const ProfileBufferControlledChunkManager::Update& a1,
    const ProfileBufferControlledChunkManager::Update& a2) {
  // Final and not-an-update don't carry other data, so we can test these two
  // states first.
  if (a1.IsFinal() || a2.IsFinal()) {
    return a1.IsFinal() && a2.IsFinal();
  }
  if (a1.IsNotUpdate() || a2.IsNotUpdate()) {
    return a1.IsNotUpdate() && a2.IsNotUpdate();
  }

  // Here, both are "normal" udpates, check member variables:

  if (a1.UnreleasedBytes() != a2.UnreleasedBytes()) {
    return false;
  }
  if (a1.ReleasedBytes() != a2.ReleasedBytes()) {
    return false;
  }
  if (a1.OldestDoneTimeStamp() != a2.OldestDoneTimeStamp()) {
    return false;
  }
  if (a1.NewlyReleasedChunksRef().size() !=
      a2.NewlyReleasedChunksRef().size()) {
    return false;
  }
  for (unsigned i = 0; i < a1.NewlyReleasedChunksRef().size(); ++i) {
    if (!IsSameMetadata(a1.NewlyReleasedChunksRef()[i],
                        a2.NewlyReleasedChunksRef()[i])) {
      return false;
    }
  }
  return true;
}

static void TestControlledChunkManagerUpdate() {
  printf("TestControlledChunkManagerUpdate...\n");

  using Update = ProfileBufferControlledChunkManager::Update;

  // Default construction.
  Update update1;
  MOZ_RELEASE_ASSERT(update1.IsNotUpdate());
  MOZ_RELEASE_ASSERT(!update1.IsFinal());

  // Clear an already-cleared update.
  update1.Clear();
  MOZ_RELEASE_ASSERT(update1.IsNotUpdate());
  MOZ_RELEASE_ASSERT(!update1.IsFinal());

  // Final construction with nullptr.
  const Update final(nullptr);
  MOZ_RELEASE_ASSERT(final.IsFinal());
  MOZ_RELEASE_ASSERT(!final.IsNotUpdate());

  // Copy final to cleared.
  update1 = final;
  MOZ_RELEASE_ASSERT(update1.IsFinal());
  MOZ_RELEASE_ASSERT(!update1.IsNotUpdate());

  // Copy final to final.
  update1 = final;
  MOZ_RELEASE_ASSERT(update1.IsFinal());
  MOZ_RELEASE_ASSERT(!update1.IsNotUpdate());

  // Clear a final update.
  update1.Clear();
  MOZ_RELEASE_ASSERT(update1.IsNotUpdate());
  MOZ_RELEASE_ASSERT(!update1.IsFinal());

  // Move final to cleared.
  update1 = Update(nullptr);
  MOZ_RELEASE_ASSERT(update1.IsFinal());
  MOZ_RELEASE_ASSERT(!update1.IsNotUpdate());

  // Move final to final.
  update1 = Update(nullptr);
  MOZ_RELEASE_ASSERT(update1.IsFinal());
  MOZ_RELEASE_ASSERT(!update1.IsNotUpdate());

  // Move from not-an-update (effectively same as Clear).
  update1 = Update();
  MOZ_RELEASE_ASSERT(update1.IsNotUpdate());
  MOZ_RELEASE_ASSERT(!update1.IsFinal());

  auto CreateBiggerChunkAfter = [](const ProfileBufferChunk& aChunkToBeat) {
    while (TimeStamp::NowUnfuzzed() <=
           aChunkToBeat.ChunkHeader().mDoneTimeStamp) {
      ::SleepMilli(1);
    }
    auto chunk = ProfileBufferChunk::Create(aChunkToBeat.BufferBytes() * 2);
    MOZ_RELEASE_ASSERT(!!chunk);
    MOZ_RELEASE_ASSERT(chunk->BufferBytes() >= aChunkToBeat.BufferBytes() * 2);
    Unused << chunk->ReserveInitialBlockAsTail(0);
    chunk->MarkDone();
    MOZ_RELEASE_ASSERT(chunk->ChunkHeader().mDoneTimeStamp >
                       aChunkToBeat.ChunkHeader().mDoneTimeStamp);
    return chunk;
  };

  update1 = Update(1, 2, nullptr, nullptr);

  // Create initial update with 2 released chunks and 1 unreleased chunk.
  auto released = ProfileBufferChunk::Create(10);
  ProfileBufferChunk* c1 = released.get();
  Unused << c1->ReserveInitialBlockAsTail(0);
  c1->MarkDone();

  released->SetLast(CreateBiggerChunkAfter(*c1));
  ProfileBufferChunk* c2 = c1->GetNext();

  auto unreleased = CreateBiggerChunkAfter(*c2);
  ProfileBufferChunk* c3 = unreleased.get();

  Update update2(c3->BufferBytes(), c1->BufferBytes() + c2->BufferBytes(), c1,
                 c1);
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update2,
      Update(c3->BufferBytes(), c1->BufferBytes() + c2->BufferBytes(),
             c1->ChunkHeader().mDoneTimeStamp,
             {{c1->ChunkHeader().mDoneTimeStamp, c1->BufferBytes()},
              {c2->ChunkHeader().mDoneTimeStamp, c2->BufferBytes()}})));
  // Check every field, this time only, after that we'll trust that the
  // `SameUpdate` test will be enough.
  MOZ_RELEASE_ASSERT(!update2.IsNotUpdate());
  MOZ_RELEASE_ASSERT(!update2.IsFinal());
  MOZ_RELEASE_ASSERT(update2.UnreleasedBytes() == c3->BufferBytes());
  MOZ_RELEASE_ASSERT(update2.ReleasedBytes() ==
                     c1->BufferBytes() + c2->BufferBytes());
  MOZ_RELEASE_ASSERT(update2.OldestDoneTimeStamp() ==
                     c1->ChunkHeader().mDoneTimeStamp);
  MOZ_RELEASE_ASSERT(update2.NewlyReleasedChunksRef().size() == 2);
  MOZ_RELEASE_ASSERT(
      IsSameMetadata(update2.NewlyReleasedChunksRef()[0],
                     {c1->ChunkHeader().mDoneTimeStamp, c1->BufferBytes()}));
  MOZ_RELEASE_ASSERT(
      IsSameMetadata(update2.NewlyReleasedChunksRef()[1],
                     {c2->ChunkHeader().mDoneTimeStamp, c2->BufferBytes()}));

  // Fold into not-an-update.
  update1.Fold(std::move(update2));
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update1,
      Update(c3->BufferBytes(), c1->BufferBytes() + c2->BufferBytes(),
             c1->ChunkHeader().mDoneTimeStamp,
             {{c1->ChunkHeader().mDoneTimeStamp, c1->BufferBytes()},
              {c2->ChunkHeader().mDoneTimeStamp, c2->BufferBytes()}})));

  // Pretend nothing happened.
  update2 = Update(c3->BufferBytes(), c1->BufferBytes() + c2->BufferBytes(), c1,
                   nullptr);
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update2, Update(c3->BufferBytes(), c1->BufferBytes() + c2->BufferBytes(),
                      c1->ChunkHeader().mDoneTimeStamp, {})));
  update1.Fold(std::move(update2));
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update1,
      Update(c3->BufferBytes(), c1->BufferBytes() + c2->BufferBytes(),
             c1->ChunkHeader().mDoneTimeStamp,
             {{c1->ChunkHeader().mDoneTimeStamp, c1->BufferBytes()},
              {c2->ChunkHeader().mDoneTimeStamp, c2->BufferBytes()}})));

  // Pretend there's a new unreleased chunk.
  c3->SetLast(CreateBiggerChunkAfter(*c3));
  ProfileBufferChunk* c4 = c3->GetNext();
  update2 = Update(c3->BufferBytes() + c4->BufferBytes(),
                   c1->BufferBytes() + c2->BufferBytes(), c1, nullptr);
  MOZ_RELEASE_ASSERT(
      IsSameUpdate(update2, Update(c3->BufferBytes() + c4->BufferBytes(),
                                   c1->BufferBytes() + c2->BufferBytes(),
                                   c1->ChunkHeader().mDoneTimeStamp, {})));
  update1.Fold(std::move(update2));
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update1,
      Update(c3->BufferBytes() + c4->BufferBytes(),
             c1->BufferBytes() + c2->BufferBytes(),
             c1->ChunkHeader().mDoneTimeStamp,
             {{c1->ChunkHeader().mDoneTimeStamp, c1->BufferBytes()},
              {c2->ChunkHeader().mDoneTimeStamp, c2->BufferBytes()}})));

  // Pretend the first unreleased chunk c3 has been released.
  released->SetLast(std::exchange(unreleased, unreleased->ReleaseNext()));
  update2 =
      Update(c4->BufferBytes(),
             c1->BufferBytes() + c2->BufferBytes() + c3->BufferBytes(), c1, c3);
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update2,
      Update(c4->BufferBytes(),
             c1->BufferBytes() + c2->BufferBytes() + c3->BufferBytes(),
             c1->ChunkHeader().mDoneTimeStamp,
             {{c3->ChunkHeader().mDoneTimeStamp, c3->BufferBytes()}})));
  update1.Fold(std::move(update2));
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update1,
      Update(c4->BufferBytes(),
             c1->BufferBytes() + c2->BufferBytes() + c3->BufferBytes(),
             c1->ChunkHeader().mDoneTimeStamp,
             {{c1->ChunkHeader().mDoneTimeStamp, c1->BufferBytes()},
              {c2->ChunkHeader().mDoneTimeStamp, c2->BufferBytes()},
              {c3->ChunkHeader().mDoneTimeStamp, c3->BufferBytes()}})));

  // Pretend c1 has been destroyed, so the oldest timestamp is now at c2.
  released = released->ReleaseNext();
  c1 = nullptr;
  update2 = Update(c4->BufferBytes(), c2->BufferBytes() + c3->BufferBytes(), c2,
                   nullptr);
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update2, Update(c4->BufferBytes(), c2->BufferBytes() + c3->BufferBytes(),
                      c2->ChunkHeader().mDoneTimeStamp, {})));
  update1.Fold(std::move(update2));
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update1,
      Update(c4->BufferBytes(), c2->BufferBytes() + c3->BufferBytes(),
             c2->ChunkHeader().mDoneTimeStamp,
             {{c2->ChunkHeader().mDoneTimeStamp, c2->BufferBytes()},
              {c3->ChunkHeader().mDoneTimeStamp, c3->BufferBytes()}})));

  // Pretend c2 has been recycled to make unreleased c5, and c4 has been
  // released.
  auto recycled = std::exchange(released, released->ReleaseNext());
  recycled->MarkRecycled();
  Unused << recycled->ReserveInitialBlockAsTail(0);
  recycled->MarkDone();
  released->SetLast(std::move(unreleased));
  unreleased = std::move(recycled);
  ProfileBufferChunk* c5 = c2;
  c2 = nullptr;
  update2 =
      Update(c5->BufferBytes(), c3->BufferBytes() + c4->BufferBytes(), c3, c4);
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update2,
      Update(c5->BufferBytes(), c3->BufferBytes() + c4->BufferBytes(),
             c3->ChunkHeader().mDoneTimeStamp,
             {{c4->ChunkHeader().mDoneTimeStamp, c4->BufferBytes()}})));
  update1.Fold(std::move(update2));
  MOZ_RELEASE_ASSERT(IsSameUpdate(
      update1,
      Update(c5->BufferBytes(), c3->BufferBytes() + c4->BufferBytes(),
             c3->ChunkHeader().mDoneTimeStamp,
             {{c3->ChunkHeader().mDoneTimeStamp, c3->BufferBytes()},
              {c4->ChunkHeader().mDoneTimeStamp, c4->BufferBytes()}})));

  // And send a final update.
  update1.Fold(Update(nullptr));
  MOZ_RELEASE_ASSERT(update1.IsFinal());
  MOZ_RELEASE_ASSERT(!update1.IsNotUpdate());

  printf("TestControlledChunkManagerUpdate done\n");
}

static void TestControlledChunkManagerWithLocalLimit() {
  printf("TestControlledChunkManagerWithLocalLimit...\n");

  // Construct a ProfileBufferChunkManagerWithLocalLimit with chunk of minimum
  // size >=100, up to 1000 bytes.
  constexpr ProfileBufferChunk::Length MaxTotalBytes = 1000;
  constexpr ProfileBufferChunk::Length ChunkMinBufferBytes = 100;
  ProfileBufferChunkManagerWithLocalLimit cmll{MaxTotalBytes,
                                               ChunkMinBufferBytes};

  // Reference to chunk manager base class.
  ProfileBufferChunkManager& cm = cmll;

  // Reference to controlled chunk manager base class.
  ProfileBufferControlledChunkManager& ccm = cmll;

#  ifdef DEBUG
  const char* chunkManagerRegisterer =
      "TestControlledChunkManagerWithLocalLimit";
  cm.RegisteredWith(chunkManagerRegisterer);
#  endif  // DEBUG

  MOZ_RELEASE_ASSERT(cm.MaxTotalSize() == MaxTotalBytes,
                     "Max total size should be exactly as given");

  unsigned destroyedChunks = 0;
  unsigned destroyedBytes = 0;
  cm.SetChunkDestroyedCallback([&](const ProfileBufferChunk& aChunks) {
    for (const ProfileBufferChunk* chunk = &aChunks; chunk;
         chunk = chunk->GetNext()) {
      destroyedChunks += 1;
      destroyedBytes += chunk->BufferBytes();
    }
  });

  using Update = ProfileBufferControlledChunkManager::Update;
  unsigned updateCount = 0;
  ProfileBufferControlledChunkManager::Update update;
  MOZ_RELEASE_ASSERT(update.IsNotUpdate());
  auto updateCallback = [&](Update&& aUpdate) {
    ++updateCount;
    update.Fold(std::move(aUpdate));
  };
  ccm.SetUpdateCallback(updateCallback);
  MOZ_RELEASE_ASSERT(updateCount == 1,
                     "SetUpdateCallback should have triggered an update");
  MOZ_RELEASE_ASSERT(IsSameUpdate(update, Update(0, 0, TimeStamp{}, {})));
  updateCount = 0;
  update.Clear();

  UniquePtr<ProfileBufferChunk> extantReleasedChunks =
      cm.GetExtantReleasedChunks();
  MOZ_RELEASE_ASSERT(!extantReleasedChunks, "Unexpected released chunk(s)");
  MOZ_RELEASE_ASSERT(updateCount == 1,
                     "GetExtantReleasedChunks should have triggered an update");
  MOZ_RELEASE_ASSERT(IsSameUpdate(update, Update(0, 0, TimeStamp{}, {})));
  updateCount = 0;
  update.Clear();

  // First request.
  UniquePtr<ProfileBufferChunk> chunk = cm.GetChunk();
  MOZ_RELEASE_ASSERT(!!chunk,
                     "First chunk immediate request should always work");
  const auto chunkActualBufferBytes = chunk->BufferBytes();
  // Keep address, for later checks.
  const uintptr_t chunk1Address = reinterpret_cast<uintptr_t>(chunk.get());
  MOZ_RELEASE_ASSERT(updateCount == 1,
                     "GetChunk should have triggered an update");
  MOZ_RELEASE_ASSERT(
      IsSameUpdate(update, Update(chunk->BufferBytes(), 0, TimeStamp{}, {})));
  updateCount = 0;
  update.Clear();

  extantReleasedChunks = cm.GetExtantReleasedChunks();
  MOZ_RELEASE_ASSERT(!extantReleasedChunks, "Unexpected released chunk(s)");
  MOZ_RELEASE_ASSERT(updateCount == 1,
                     "GetExtantReleasedChunks should have triggered an update");
  MOZ_RELEASE_ASSERT(
      IsSameUpdate(update, Update(chunk->BufferBytes(), 0, TimeStamp{}, {})));
  updateCount = 0;
  update.Clear();

  // For this test, we need to be able to get at least 2 chunks without hitting
  // the limit. (If this failed, it wouldn't necessary be a problem with
  // ProfileBufferChunkManagerWithLocalLimit, fiddle with constants at the top
  // of this test.)
  MOZ_RELEASE_ASSERT(chunkActualBufferBytes < 2 * MaxTotalBytes);

  ProfileBufferChunk::Length previousUnreleasedBytes = chunk->BufferBytes();
  ProfileBufferChunk::Length previousReleasedBytes = 0;
  TimeStamp previousOldestDoneTimeStamp;

  unsigned chunk1ReuseCount = 0;

  // We will do enough loops to go through the maximum size a number of times.
  const unsigned Rollovers = 3;
  const unsigned Loops = Rollovers * MaxTotalBytes / chunkActualBufferBytes;
  for (unsigned i = 0; i < Loops; ++i) {
    // Add some data to the chunk.
    const ProfileBufferIndex index =
        ProfileBufferIndex(chunkActualBufferBytes) * i + 1;
    chunk->SetRangeStart(index);
    Unused << chunk->ReserveInitialBlockAsTail(1);
    Unused << chunk->ReserveBlock(2);

    // Request a new chunk.
    UniquePtr<ProfileBufferChunk> newChunk;
    cm.RequestChunk([&](UniquePtr<ProfileBufferChunk> aChunk) {
      newChunk = std::move(aChunk);
    });
    MOZ_RELEASE_ASSERT(updateCount == 0,
                       "RequestChunk() shouldn't have triggered an update");
    cm.FulfillChunkRequests();
    MOZ_RELEASE_ASSERT(!!newChunk, "Chunk request should always work");
    MOZ_RELEASE_ASSERT(newChunk->BufferBytes() == chunkActualBufferBytes,
                       "Unexpected chunk size");
    MOZ_RELEASE_ASSERT(!newChunk->GetNext(), "There should only be one chunk");

    MOZ_RELEASE_ASSERT(updateCount == 1,
                       "FulfillChunkRequests() after a request should have "
                       "triggered an update");
    MOZ_RELEASE_ASSERT(!update.IsFinal());
    MOZ_RELEASE_ASSERT(!update.IsNotUpdate());
    MOZ_RELEASE_ASSERT(update.UnreleasedBytes() ==
                       previousUnreleasedBytes + newChunk->BufferBytes());
    previousUnreleasedBytes = update.UnreleasedBytes();
    MOZ_RELEASE_ASSERT(update.ReleasedBytes() <= previousReleasedBytes);
    previousReleasedBytes = update.ReleasedBytes();
    MOZ_RELEASE_ASSERT(previousOldestDoneTimeStamp.IsNull() ||
                       update.OldestDoneTimeStamp() >=
                           previousOldestDoneTimeStamp);
    previousOldestDoneTimeStamp = update.OldestDoneTimeStamp();
    MOZ_RELEASE_ASSERT(update.NewlyReleasedChunksRef().empty());
    updateCount = 0;
    update.Clear();

    // Make sure the "Done" timestamp below cannot be the same as from the
    // previous loop.
    const TimeStamp now = TimeStamp::NowUnfuzzed();
    while (TimeStamp::NowUnfuzzed() == now) {
      ::SleepMilli(1);
    }

    // Mark previous chunk done and release it.
    chunk->MarkDone();
    const auto doneTimeStamp = chunk->ChunkHeader().mDoneTimeStamp;
    const auto bufferBytes = chunk->BufferBytes();
    cm.ReleaseChunks(std::move(chunk));

    MOZ_RELEASE_ASSERT(updateCount == 1,
                       "ReleaseChunks() should have triggered an update");
    MOZ_RELEASE_ASSERT(!update.IsFinal());
    MOZ_RELEASE_ASSERT(!update.IsNotUpdate());
    MOZ_RELEASE_ASSERT(update.UnreleasedBytes() ==
                       previousUnreleasedBytes - bufferBytes);
    previousUnreleasedBytes = update.UnreleasedBytes();
    MOZ_RELEASE_ASSERT(update.ReleasedBytes() ==
                       previousReleasedBytes + bufferBytes);
    previousReleasedBytes = update.ReleasedBytes();
    MOZ_RELEASE_ASSERT(previousOldestDoneTimeStamp.IsNull() ||
                       update.OldestDoneTimeStamp() >=
                           previousOldestDoneTimeStamp);
    previousOldestDoneTimeStamp = update.OldestDoneTimeStamp();
    MOZ_RELEASE_ASSERT(update.OldestDoneTimeStamp() <= doneTimeStamp);
    MOZ_RELEASE_ASSERT(update.NewlyReleasedChunksRef().size() == 1);
    MOZ_RELEASE_ASSERT(update.NewlyReleasedChunksRef()[0].mDoneTimeStamp ==
                       doneTimeStamp);
    MOZ_RELEASE_ASSERT(update.NewlyReleasedChunksRef()[0].mBufferBytes ==
                       bufferBytes);
    updateCount = 0;
    update.Clear();

    // And cycle to the new chunk.
    chunk = std::move(newChunk);

    if (reinterpret_cast<uintptr_t>(chunk.get()) == chunk1Address) {
      ++chunk1ReuseCount;
    }
  }

  // Enough testing! Clean-up.
  Unused << chunk->ReserveInitialBlockAsTail(0);
  chunk->MarkDone();
  cm.ForgetUnreleasedChunks();
  MOZ_RELEASE_ASSERT(
      updateCount == 1,
      "ForgetUnreleasedChunks() should have triggered an update");
  MOZ_RELEASE_ASSERT(!update.IsFinal());
  MOZ_RELEASE_ASSERT(!update.IsNotUpdate());
  MOZ_RELEASE_ASSERT(update.UnreleasedBytes() == 0);
  MOZ_RELEASE_ASSERT(update.ReleasedBytes() == previousReleasedBytes);
  MOZ_RELEASE_ASSERT(update.NewlyReleasedChunksRef().empty() == 1);
  updateCount = 0;
  update.Clear();

  ccm.SetUpdateCallback({});
  MOZ_RELEASE_ASSERT(updateCount == 1,
                     "SetUpdateCallback({}) should have triggered an update");
  MOZ_RELEASE_ASSERT(update.IsFinal());

#  ifdef DEBUG
  cm.DeregisteredFrom(chunkManagerRegisterer);
#  endif  // DEBUG

  printf("TestControlledChunkManagerWithLocalLimit done\n");
}

static void TestChunkedBuffer() {
  printf("TestChunkedBuffer...\n");

  ProfileBufferBlockIndex blockIndex;
  MOZ_RELEASE_ASSERT(!blockIndex);
  MOZ_RELEASE_ASSERT(blockIndex == nullptr);

  // Create an out-of-session ProfileChunkedBuffer.
  ProfileChunkedBuffer cb(ProfileChunkedBuffer::ThreadSafety::WithMutex);

  MOZ_RELEASE_ASSERT(cb.BufferLength().isNothing());

  int result = 0;
  result = cb.ReserveAndPut(
      []() {
        MOZ_RELEASE_ASSERT(false);
        return 1;
      },
      [](Maybe<ProfileBufferEntryWriter>& aEW) { return aEW ? 2 : 3; });
  MOZ_RELEASE_ASSERT(result == 3);

  result = 0;
  result = cb.Put(
      1, [](Maybe<ProfileBufferEntryWriter>& aEW) { return aEW ? 1 : 2; });
  MOZ_RELEASE_ASSERT(result == 2);

  blockIndex = cb.PutFrom(&result, 1);
  MOZ_RELEASE_ASSERT(!blockIndex);

  blockIndex = cb.PutObjects(123, result, "hello");
  MOZ_RELEASE_ASSERT(!blockIndex);

  blockIndex = cb.PutObject(123);
  MOZ_RELEASE_ASSERT(!blockIndex);

  auto chunks = cb.GetAllChunks();
  static_assert(std::is_same_v<decltype(chunks), UniquePtr<ProfileBufferChunk>>,
                "ProfileChunkedBuffer::GetAllChunks() should return a "
                "UniquePtr<ProfileBufferChunk>");
  MOZ_RELEASE_ASSERT(!chunks, "Expected no chunks when out-of-session");

  bool ran = false;
  result = 0;
  result = cb.Read([&](ProfileChunkedBuffer::Reader* aReader) {
    ran = true;
    MOZ_RELEASE_ASSERT(!aReader);
    return 3;
  });
  MOZ_RELEASE_ASSERT(ran);
  MOZ_RELEASE_ASSERT(result == 3);

  cb.ReadEach([](ProfileBufferEntryReader&) { MOZ_RELEASE_ASSERT(false); });

  result = 0;
  result = cb.ReadAt(nullptr, [](Maybe<ProfileBufferEntryReader>&& er) {
    MOZ_RELEASE_ASSERT(er.isNothing());
    return 4;
  });
  MOZ_RELEASE_ASSERT(result == 4);

  // Use ProfileBufferChunkManagerWithLocalLimit, which will give away
  // ProfileBufferChunks that can contain 128 bytes, using up to 1KB of memory
  // (including usable 128 bytes and headers).
  constexpr size_t bufferMaxSize = 1024;
  constexpr ProfileChunkedBuffer::Length chunkMinSize = 128;
  ProfileBufferChunkManagerWithLocalLimit cm(bufferMaxSize, chunkMinSize);
  cb.SetChunkManager(cm);

  // Let the chunk manager fulfill the initial request for an extra chunk.
  cm.FulfillChunkRequests();

  MOZ_RELEASE_ASSERT(cm.MaxTotalSize() == bufferMaxSize);
  MOZ_RELEASE_ASSERT(cb.BufferLength().isSome());
  MOZ_RELEASE_ASSERT(*cb.BufferLength() == bufferMaxSize);

  // Write an int with the main `ReserveAndPut` function.
  const int test = 123;
  ran = false;
  blockIndex = nullptr;
  bool success = cb.ReserveAndPut(
      []() { return sizeof(test); },
      [&](Maybe<ProfileBufferEntryWriter>& aEW) {
        ran = true;
        if (!aEW) {
          return false;
        }
        blockIndex = aEW->CurrentBlockIndex();
        MOZ_RELEASE_ASSERT(aEW->RemainingBytes() == sizeof(test));
        aEW->WriteObject(test);
        MOZ_RELEASE_ASSERT(aEW->RemainingBytes() == 0);
        return true;
      });
  MOZ_RELEASE_ASSERT(ran);
  MOZ_RELEASE_ASSERT(success);
  MOZ_RELEASE_ASSERT(blockIndex.ConvertToProfileBufferIndex() == 1);

  ran = false;
  result = 0;
  result = cb.Read([&](ProfileChunkedBuffer::Reader* aReader) {
    ran = true;
    MOZ_RELEASE_ASSERT(!!aReader);
    // begin() and end() should be at the range edges (verified above).
    MOZ_RELEASE_ASSERT(
        aReader->begin().CurrentBlockIndex().ConvertToProfileBufferIndex() ==
        1);
    MOZ_RELEASE_ASSERT(
        aReader->end().CurrentBlockIndex().ConvertToProfileBufferIndex() == 0);
    // Null ProfileBufferBlockIndex clamped to the beginning.
    MOZ_RELEASE_ASSERT(aReader->At(nullptr) == aReader->begin());
    MOZ_RELEASE_ASSERT(aReader->At(blockIndex) == aReader->begin());
    // At(begin) same as begin().
    MOZ_RELEASE_ASSERT(aReader->At(aReader->begin().CurrentBlockIndex()) ==
                       aReader->begin());
    // At(past block) same as end().
    MOZ_RELEASE_ASSERT(
        aReader->At(ProfileBufferBlockIndex::CreateFromProfileBufferIndex(
            1 + 1 + sizeof(test))) == aReader->end());

    size_t read = 0;
    aReader->ForEach([&](ProfileBufferEntryReader& er) {
      ++read;
      MOZ_RELEASE_ASSERT(er.RemainingBytes() == sizeof(test));
      const auto value = er.ReadObject<decltype(test)>();
      MOZ_RELEASE_ASSERT(value == test);
      MOZ_RELEASE_ASSERT(er.RemainingBytes() == 0);
    });
    MOZ_RELEASE_ASSERT(read == 1);

    read = 0;
    for (auto er : *aReader) {
      static_assert(std::is_same_v<decltype(er), ProfileBufferEntryReader>,
                    "ProfileChunkedBuffer::Reader range-for should produce "
                    "ProfileBufferEntryReader objects");
      ++read;
      MOZ_RELEASE_ASSERT(er.RemainingBytes() == sizeof(test));
      const auto value = er.ReadObject<decltype(test)>();
      MOZ_RELEASE_ASSERT(value == test);
      MOZ_RELEASE_ASSERT(er.RemainingBytes() == 0);
    };
    MOZ_RELEASE_ASSERT(read == 1);
    return 5;
  });
  MOZ_RELEASE_ASSERT(ran);
  MOZ_RELEASE_ASSERT(result == 5);

  // Read the int directly from the ProfileChunkedBuffer, without block index.
  size_t read = 0;
  cb.ReadEach([&](ProfileBufferEntryReader& er) {
    ++read;
    MOZ_RELEASE_ASSERT(er.RemainingBytes() == sizeof(test));
    const auto value = er.ReadObject<decltype(test)>();
    MOZ_RELEASE_ASSERT(value == test);
    MOZ_RELEASE_ASSERT(er.RemainingBytes() == 0);
  });
  MOZ_RELEASE_ASSERT(read == 1);

  // Read the int directly from the ProfileChunkedBuffer, with block index.
  read = 0;
  blockIndex = nullptr;
  cb.ReadEach(
      [&](ProfileBufferEntryReader& er, ProfileBufferBlockIndex aBlockIndex) {
        ++read;
        MOZ_RELEASE_ASSERT(!!aBlockIndex);
        MOZ_RELEASE_ASSERT(!blockIndex);
        blockIndex = aBlockIndex;
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == sizeof(test));
        const auto value = er.ReadObject<decltype(test)>();
        MOZ_RELEASE_ASSERT(value == test);
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == 0);
      });
  MOZ_RELEASE_ASSERT(read == 1);
  MOZ_RELEASE_ASSERT(!!blockIndex);
  MOZ_RELEASE_ASSERT(blockIndex != nullptr);

  // Read the int from its block index.
  read = 0;
  result = 0;
  result = cb.ReadAt(blockIndex, [&](Maybe<ProfileBufferEntryReader>&& er) {
    ++read;
    MOZ_RELEASE_ASSERT(er.isSome());
    MOZ_RELEASE_ASSERT(er->CurrentBlockIndex() == blockIndex);
    MOZ_RELEASE_ASSERT(!er->NextBlockIndex());
    MOZ_RELEASE_ASSERT(er->RemainingBytes() == sizeof(test));
    const auto value = er->ReadObject<decltype(test)>();
    MOZ_RELEASE_ASSERT(value == test);
    MOZ_RELEASE_ASSERT(er->RemainingBytes() == 0);
    return 6;
  });
  MOZ_RELEASE_ASSERT(result == 6);
  MOZ_RELEASE_ASSERT(read == 1);

  // Steal the underlying ProfileBufferChunks from the ProfileChunkedBuffer.
  chunks = cb.GetAllChunks();
  MOZ_RELEASE_ASSERT(!!chunks, "Expected at least one chunk");
  MOZ_RELEASE_ASSERT(!!chunks->GetNext(), "Expected two chunks");
  MOZ_RELEASE_ASSERT(!chunks->GetNext()->GetNext(), "Expected only two chunks");
  const ProfileChunkedBuffer::Length chunkActualSize = chunks->BufferBytes();
  MOZ_RELEASE_ASSERT(chunkActualSize >= chunkMinSize);
  MOZ_RELEASE_ASSERT(chunks->RangeStart() == 1);
  MOZ_RELEASE_ASSERT(chunks->OffsetFirstBlock() == 0);
  MOZ_RELEASE_ASSERT(chunks->OffsetPastLastBlock() == 1 + sizeof(test));

  // Nothing more to read from the now-empty ProfileChunkedBuffer.
  cb.ReadEach([](ProfileBufferEntryReader&) { MOZ_RELEASE_ASSERT(false); });
  cb.ReadEach([](ProfileBufferEntryReader&, ProfileBufferBlockIndex) {
    MOZ_RELEASE_ASSERT(false);
  });
  result = 0;
  result = cb.ReadAt(nullptr, [](Maybe<ProfileBufferEntryReader>&& er) {
    MOZ_RELEASE_ASSERT(er.isNothing());
    return 7;
  });
  MOZ_RELEASE_ASSERT(result == 7);

  // Read the int from the stolen chunks.
  read = 0;
  ProfileChunkedBuffer::ReadEach(
      chunks.get(), nullptr,
      [&](ProfileBufferEntryReader& er, ProfileBufferBlockIndex aBlockIndex) {
        ++read;
        MOZ_RELEASE_ASSERT(aBlockIndex == blockIndex);
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == sizeof(test));
        const auto value = er.ReadObject<decltype(test)>();
        MOZ_RELEASE_ASSERT(value == test);
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == 0);
      });
  MOZ_RELEASE_ASSERT(read == 1);

  // Write lots of numbers (by memcpy), which should trigger Chunk destructions.
  ProfileBufferBlockIndex firstBlockIndex;
  MOZ_RELEASE_ASSERT(!firstBlockIndex);
  ProfileBufferBlockIndex lastBlockIndex;
  MOZ_RELEASE_ASSERT(!lastBlockIndex);
  const size_t lots = 2 * bufferMaxSize / (1 + sizeof(int));
  for (size_t i = 1; i < lots; ++i) {
    ProfileBufferBlockIndex blockIndex = cb.PutFrom(&i, sizeof(i));
    MOZ_RELEASE_ASSERT(!!blockIndex);
    MOZ_RELEASE_ASSERT(blockIndex > firstBlockIndex);
    if (!firstBlockIndex) {
      firstBlockIndex = blockIndex;
    }
    MOZ_RELEASE_ASSERT(blockIndex > lastBlockIndex);
    lastBlockIndex = blockIndex;
  }

  // Read extant numbers, which should at least follow each other.
  read = 0;
  size_t i = 0;
  cb.ReadEach(
      [&](ProfileBufferEntryReader& er, ProfileBufferBlockIndex aBlockIndex) {
        ++read;
        MOZ_RELEASE_ASSERT(!!aBlockIndex);
        MOZ_RELEASE_ASSERT(aBlockIndex > firstBlockIndex);
        MOZ_RELEASE_ASSERT(aBlockIndex <= lastBlockIndex);
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == sizeof(size_t));
        const auto value = er.ReadObject<size_t>();
        if (i == 0) {
          i = value;
        } else {
          MOZ_RELEASE_ASSERT(value == ++i);
        }
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == 0);
      });
  MOZ_RELEASE_ASSERT(read != 0);
  MOZ_RELEASE_ASSERT(read < lots);

  // Read first extant number.
  read = 0;
  i = 0;
  blockIndex = nullptr;
  success =
      cb.ReadAt(firstBlockIndex, [&](Maybe<ProfileBufferEntryReader>&& er) {
        MOZ_ASSERT(er.isSome());
        ++read;
        MOZ_RELEASE_ASSERT(er->CurrentBlockIndex() > firstBlockIndex);
        MOZ_RELEASE_ASSERT(!!er->NextBlockIndex());
        MOZ_RELEASE_ASSERT(er->NextBlockIndex() > firstBlockIndex);
        MOZ_RELEASE_ASSERT(er->NextBlockIndex() < lastBlockIndex);
        blockIndex = er->NextBlockIndex();
        MOZ_RELEASE_ASSERT(er->RemainingBytes() == sizeof(size_t));
        const auto value = er->ReadObject<size_t>();
        MOZ_RELEASE_ASSERT(i == 0);
        i = value;
        MOZ_RELEASE_ASSERT(er->RemainingBytes() == 0);
        return 7;
      });
  MOZ_RELEASE_ASSERT(success);
  MOZ_RELEASE_ASSERT(read == 1);
  // Read other extant numbers one by one.
  do {
    bool success =
        cb.ReadAt(blockIndex, [&](Maybe<ProfileBufferEntryReader>&& er) {
          MOZ_ASSERT(er.isSome());
          ++read;
          MOZ_RELEASE_ASSERT(er->CurrentBlockIndex() == blockIndex);
          MOZ_RELEASE_ASSERT(!er->NextBlockIndex() ||
                             er->NextBlockIndex() > blockIndex);
          MOZ_RELEASE_ASSERT(!er->NextBlockIndex() ||
                             er->NextBlockIndex() > firstBlockIndex);
          MOZ_RELEASE_ASSERT(!er->NextBlockIndex() ||
                             er->NextBlockIndex() <= lastBlockIndex);
          MOZ_RELEASE_ASSERT(er->NextBlockIndex()
                                 ? blockIndex < lastBlockIndex
                                 : blockIndex == lastBlockIndex,
                             "er->NextBlockIndex() should only be null when "
                             "blockIndex is at the last block");
          blockIndex = er->NextBlockIndex();
          MOZ_RELEASE_ASSERT(er->RemainingBytes() == sizeof(size_t));
          const auto value = er->ReadObject<size_t>();
          MOZ_RELEASE_ASSERT(value == ++i);
          MOZ_RELEASE_ASSERT(er->RemainingBytes() == 0);
          return true;
        });
    MOZ_RELEASE_ASSERT(success);
  } while (blockIndex);
  MOZ_RELEASE_ASSERT(read > 1);

#  ifdef DEBUG
  // cb.Dump();
#  endif

  cb.Clear();

#  ifdef DEBUG
  // cb.Dump();
#  endif

  // Start writer threads.
  constexpr int ThreadCount = 32;
  std::thread threads[ThreadCount];
  for (int threadNo = 0; threadNo < ThreadCount; ++threadNo) {
    threads[threadNo] = std::thread(
        [&](int aThreadNo) {
          ::SleepMilli(1);
          constexpr int pushCount = 1024;
          for (int push = 0; push < pushCount; ++push) {
            // Reserve as many bytes as the thread number (but at least enough
            // to store an int), and write an increasing int.
            const bool success =
                cb.Put(std::max(aThreadNo, int(sizeof(push))),
                       [&](Maybe<ProfileBufferEntryWriter>& aEW) {
                         if (!aEW) {
                           return false;
                         }
                         aEW->WriteObject(aThreadNo * 1000000 + push);
                         // Advance writer to the end.
                         for (size_t r = aEW->RemainingBytes(); r != 0; --r) {
                           aEW->WriteObject<char>('_');
                         }
                         return true;
                       });
            MOZ_RELEASE_ASSERT(success);
          }
        },
        threadNo);
  }

  // Wait for all writer threads to die.
  for (auto&& thread : threads) {
    thread.join();
  }

#  ifdef DEBUG
  // cb.Dump();
#  endif

  // Reset to out-of-session.
  cb.ResetChunkManager();

  success = cb.ReserveAndPut(
      []() {
        MOZ_RELEASE_ASSERT(false);
        return 1;
      },
      [](Maybe<ProfileBufferEntryWriter>& aEW) { return !!aEW; });
  MOZ_RELEASE_ASSERT(!success);

  success =
      cb.Put(1, [](Maybe<ProfileBufferEntryWriter>& aEW) { return !!aEW; });
  MOZ_RELEASE_ASSERT(!success);

  blockIndex = cb.PutFrom(&success, 1);
  MOZ_RELEASE_ASSERT(!blockIndex);

  blockIndex = cb.PutObjects(123, success, "hello");
  MOZ_RELEASE_ASSERT(!blockIndex);

  blockIndex = cb.PutObject(123);
  MOZ_RELEASE_ASSERT(!blockIndex);

  chunks = cb.GetAllChunks();
  MOZ_RELEASE_ASSERT(!chunks, "Expected no chunks when out-of-session");

  cb.ReadEach([](ProfileBufferEntryReader&) { MOZ_RELEASE_ASSERT(false); });

  success = cb.ReadAt(nullptr, [](Maybe<ProfileBufferEntryReader>&& er) {
    MOZ_RELEASE_ASSERT(er.isNothing());
    return true;
  });
  MOZ_RELEASE_ASSERT(success);

  printf("TestChunkedBuffer done\n");
}

static void TestChunkedBufferSingle() {
  printf("TestChunkedBufferSingle...\n");

  constexpr ProfileChunkedBuffer::Length chunkMinSize = 128;

  // Create a ProfileChunkedBuffer that will own&use a
  // ProfileBufferChunkManagerSingle, which will give away one
  // ProfileBufferChunk that can contain 128 bytes.
  ProfileChunkedBuffer cbSingle(
      ProfileChunkedBuffer::ThreadSafety::WithoutMutex,
      MakeUnique<ProfileBufferChunkManagerSingle>(chunkMinSize));

  MOZ_RELEASE_ASSERT(cbSingle.BufferLength().isSome());
  MOZ_RELEASE_ASSERT(*cbSingle.BufferLength() >= chunkMinSize);

  // Write lots of numbers (as objects), which should trigger the release of our
  // single Chunk.
  size_t firstIndexToFail = 0;
  ProfileBufferBlockIndex lastBlockIndex;
  for (size_t i = 1; i < 3 * chunkMinSize / (1 + sizeof(int)); ++i) {
    ProfileBufferBlockIndex blockIndex = cbSingle.PutObject(i);
    if (blockIndex) {
      MOZ_RELEASE_ASSERT(
          firstIndexToFail == 0,
          "We should successfully write after we have failed once");
      lastBlockIndex = blockIndex;
    } else if (firstIndexToFail == 0) {
      firstIndexToFail = i;
    }
  }
  MOZ_RELEASE_ASSERT(firstIndexToFail != 0,
                     "There should be at least one failure");
  MOZ_RELEASE_ASSERT(firstIndexToFail != 1, "We shouldn't fail from the start");
  MOZ_RELEASE_ASSERT(!!lastBlockIndex, "We shouldn't fail from the start");

  // Read extant numbers, which should go from 1 to firstIndexToFail-1.
  size_t read = 0;
  cbSingle.ReadEach(
      [&](ProfileBufferEntryReader& er, ProfileBufferBlockIndex blockIndex) {
        ++read;
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == sizeof(size_t));
        const auto value = er.ReadObject<size_t>();
        MOZ_RELEASE_ASSERT(value == read);
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == 0);
        MOZ_RELEASE_ASSERT(blockIndex <= lastBlockIndex,
                           "Unexpected block index past the last written one");
      });
  MOZ_RELEASE_ASSERT(read == firstIndexToFail - 1,
                     "We should have read up to before the first failure");

  // Test AppendContent:
  // Create another ProfileChunkedBuffer that will use a
  // ProfileBufferChunkManagerWithLocalLimit, which will give away
  // ProfileBufferChunks that can contain 128 bytes, using up to 1KB of memory
  // (including usable 128 bytes and headers).
  constexpr size_t bufferMaxSize = 1024;
  ProfileBufferChunkManagerWithLocalLimit cmTarget(bufferMaxSize, chunkMinSize);
  ProfileChunkedBuffer cbTarget(ProfileChunkedBuffer::ThreadSafety::WithMutex,
                                cmTarget);

  // It should start empty.
  cbTarget.ReadEach(
      [](ProfileBufferEntryReader&) { MOZ_RELEASE_ASSERT(false); });

  // Copy the contents from cbSingle to cbTarget.
  cbTarget.AppendContents(cbSingle);

  // And verify that we now have the same contents in cbTarget.
  read = 0;
  cbTarget.ReadEach(
      [&](ProfileBufferEntryReader& er, ProfileBufferBlockIndex blockIndex) {
        ++read;
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == sizeof(size_t));
        const auto value = er.ReadObject<size_t>();
        MOZ_RELEASE_ASSERT(value == read);
        MOZ_RELEASE_ASSERT(er.RemainingBytes() == 0);
        MOZ_RELEASE_ASSERT(blockIndex <= lastBlockIndex,
                           "Unexpected block index past the last written one");
      });
  MOZ_RELEASE_ASSERT(read == firstIndexToFail - 1,
                     "We should have read up to before the first failure");

#  ifdef DEBUG
  // cbSingle.Dump();
  // cbTarget.Dump();
#  endif

  printf("TestChunkedBufferSingle done\n");
}

static void TestModuloBuffer(ModuloBuffer<>& mb, uint32_t MBSize) {
  using MB = ModuloBuffer<>;

  MOZ_RELEASE_ASSERT(mb.BufferLength().Value() == MBSize);

  // Iterator comparisons.
  MOZ_RELEASE_ASSERT(mb.ReaderAt(2) == mb.ReaderAt(2));
  MOZ_RELEASE_ASSERT(mb.ReaderAt(2) != mb.ReaderAt(3));
  MOZ_RELEASE_ASSERT(mb.ReaderAt(2) < mb.ReaderAt(3));
  MOZ_RELEASE_ASSERT(mb.ReaderAt(2) <= mb.ReaderAt(2));
  MOZ_RELEASE_ASSERT(mb.ReaderAt(2) <= mb.ReaderAt(3));
  MOZ_RELEASE_ASSERT(mb.ReaderAt(3) > mb.ReaderAt(2));
  MOZ_RELEASE_ASSERT(mb.ReaderAt(2) >= mb.ReaderAt(2));
  MOZ_RELEASE_ASSERT(mb.ReaderAt(3) >= mb.ReaderAt(2));

  // Iterators indices don't wrap around (even though they may be pointing at
  // the same location).
  MOZ_RELEASE_ASSERT(mb.ReaderAt(2) != mb.ReaderAt(MBSize + 2));
  MOZ_RELEASE_ASSERT(mb.ReaderAt(MBSize + 2) != mb.ReaderAt(2));

  // Dereference.
  static_assert(std::is_same<decltype(*mb.ReaderAt(0)), const MB::Byte&>::value,
                "Dereferencing from a reader should return const Byte*");
  static_assert(std::is_same<decltype(*mb.WriterAt(0)), MB::Byte&>::value,
                "Dereferencing from a writer should return Byte*");
  // Contiguous between 0 and MBSize-1.
  MOZ_RELEASE_ASSERT(&*mb.ReaderAt(MBSize - 1) ==
                     &*mb.ReaderAt(0) + (MBSize - 1));
  // Wraps around.
  MOZ_RELEASE_ASSERT(&*mb.ReaderAt(MBSize) == &*mb.ReaderAt(0));
  MOZ_RELEASE_ASSERT(&*mb.ReaderAt(MBSize + MBSize - 1) ==
                     &*mb.ReaderAt(MBSize - 1));
  MOZ_RELEASE_ASSERT(&*mb.ReaderAt(MBSize + MBSize) == &*mb.ReaderAt(0));
  // Power of 2 modulo wrapping.
  MOZ_RELEASE_ASSERT(&*mb.ReaderAt(uint32_t(-1)) == &*mb.ReaderAt(MBSize - 1));
  MOZ_RELEASE_ASSERT(&*mb.ReaderAt(static_cast<MB::Index>(-1)) ==
                     &*mb.ReaderAt(MBSize - 1));

  // Arithmetic.
  MB::Reader arit = mb.ReaderAt(0);
  MOZ_RELEASE_ASSERT(++arit == mb.ReaderAt(1));
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(1));

  MOZ_RELEASE_ASSERT(--arit == mb.ReaderAt(0));
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(0));

  MOZ_RELEASE_ASSERT(arit++ == mb.ReaderAt(0));
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(1));

  MOZ_RELEASE_ASSERT(arit-- == mb.ReaderAt(1));
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(0));

  MOZ_RELEASE_ASSERT(arit + 3 == mb.ReaderAt(3));
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(0));

  MOZ_RELEASE_ASSERT(4 + arit == mb.ReaderAt(4));
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(0));

  // (Can't have assignments inside asserts, hence the split.)
  const bool checkPlusEq = ((arit += 3) == mb.ReaderAt(3));
  MOZ_RELEASE_ASSERT(checkPlusEq);
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(3));

  MOZ_RELEASE_ASSERT((arit - 2) == mb.ReaderAt(1));
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(3));

  const bool checkMinusEq = ((arit -= 2) == mb.ReaderAt(1));
  MOZ_RELEASE_ASSERT(checkMinusEq);
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(1));

  // Random access.
  MOZ_RELEASE_ASSERT(&arit[3] == &*(arit + 3));
  MOZ_RELEASE_ASSERT(arit == mb.ReaderAt(1));

  // Iterator difference.
  MOZ_RELEASE_ASSERT(mb.ReaderAt(3) - mb.ReaderAt(1) == 2);
  MOZ_RELEASE_ASSERT(mb.ReaderAt(1) - mb.ReaderAt(3) == MB::Index(-2));

  // Only testing Writer, as Reader is just a subset with no code differences.
  MB::Writer it = mb.WriterAt(0);
  MOZ_RELEASE_ASSERT(it.CurrentIndex() == 0);

  // Write two characters at the start.
  it.WriteObject('x');
  it.WriteObject('y');

  // Backtrack to read them.
  it -= 2;
  // PeekObject should read without moving.
  MOZ_RELEASE_ASSERT(it.PeekObject<char>() == 'x');
  MOZ_RELEASE_ASSERT(it.CurrentIndex() == 0);
  // ReadObject should read and move past the character.
  MOZ_RELEASE_ASSERT(it.ReadObject<char>() == 'x');
  MOZ_RELEASE_ASSERT(it.CurrentIndex() == 1);
  MOZ_RELEASE_ASSERT(it.PeekObject<char>() == 'y');
  MOZ_RELEASE_ASSERT(it.CurrentIndex() == 1);
  MOZ_RELEASE_ASSERT(it.ReadObject<char>() == 'y');
  MOZ_RELEASE_ASSERT(it.CurrentIndex() == 2);

  // Checking that a reader can be created from a writer.
  MB::Reader it2(it);
  MOZ_RELEASE_ASSERT(it2.CurrentIndex() == 2);
  // Or assigned.
  it2 = it;
  MOZ_RELEASE_ASSERT(it2.CurrentIndex() == 2);

  // Iterator traits.
  static_assert(std::is_same<std::iterator_traits<MB::Reader>::difference_type,
                             MB::Index>::value,
                "ModuloBuffer::Reader::difference_type should be Index");
  static_assert(std::is_same<std::iterator_traits<MB::Reader>::value_type,
                             MB::Byte>::value,
                "ModuloBuffer::Reader::value_type should be Byte");
  static_assert(std::is_same<std::iterator_traits<MB::Reader>::pointer,
                             const MB::Byte*>::value,
                "ModuloBuffer::Reader::pointer should be const Byte*");
  static_assert(std::is_same<std::iterator_traits<MB::Reader>::reference,
                             const MB::Byte&>::value,
                "ModuloBuffer::Reader::reference should be const Byte&");
  static_assert(std::is_base_of<
                    std::input_iterator_tag,
                    std::iterator_traits<MB::Reader>::iterator_category>::value,
                "ModuloBuffer::Reader::iterator_category should be derived "
                "from input_iterator_tag");
  static_assert(std::is_base_of<
                    std::forward_iterator_tag,
                    std::iterator_traits<MB::Reader>::iterator_category>::value,
                "ModuloBuffer::Reader::iterator_category should be derived "
                "from forward_iterator_tag");
  static_assert(std::is_base_of<
                    std::bidirectional_iterator_tag,
                    std::iterator_traits<MB::Reader>::iterator_category>::value,
                "ModuloBuffer::Reader::iterator_category should be derived "
                "from bidirectional_iterator_tag");
  static_assert(
      std::is_same<std::iterator_traits<MB::Reader>::iterator_category,
                   std::random_access_iterator_tag>::value,
      "ModuloBuffer::Reader::iterator_category should be "
      "random_access_iterator_tag");

  // Use as input iterator by std::string constructor (which is only considered
  // with proper input iterators.)
  std::string s(mb.ReaderAt(0), mb.ReaderAt(2));
  MOZ_RELEASE_ASSERT(s == "xy");

  // Write 4-byte number at index 2.
  it.WriteObject(int32_t(123));
  MOZ_RELEASE_ASSERT(it.CurrentIndex() == 6);
  // And another, which should now wrap around (but index continues on.)
  it.WriteObject(int32_t(456));
  MOZ_RELEASE_ASSERT(it.CurrentIndex() == MBSize + 2);
  // Even though index==MBSize+2, we can read the object we wrote at 2.
  MOZ_RELEASE_ASSERT(it.ReadObject<int32_t>() == 123);
  MOZ_RELEASE_ASSERT(it.CurrentIndex() == MBSize + 6);
  // And similarly, index MBSize+6 points at the same location as index 6.
  MOZ_RELEASE_ASSERT(it.ReadObject<int32_t>() == 456);
  MOZ_RELEASE_ASSERT(it.CurrentIndex() == MBSize + MBSize + 2);
}

void TestModuloBuffer() {
  printf("TestModuloBuffer...\n");

  // Testing ModuloBuffer with default template arguments.
  using MB = ModuloBuffer<>;

  // Only 8-byte buffers, to easily test wrap-around.
  constexpr uint32_t MBSize = 8;

  // MB with self-allocated heap buffer.
  MB mbByLength(MakePowerOfTwo32<MBSize>());
  TestModuloBuffer(mbByLength, MBSize);

  // MB taking ownership of a provided UniquePtr to a buffer.
  auto uniqueBuffer = MakeUnique<uint8_t[]>(MBSize);
  MB mbByUniquePtr(MakeUnique<uint8_t[]>(MBSize), MakePowerOfTwo32<MBSize>());
  TestModuloBuffer(mbByUniquePtr, MBSize);

  // MB using part of a buffer on the stack. The buffer is three times the
  // required size: The middle third is where ModuloBuffer will work, the first
  // and last thirds are only used to later verify that ModuloBuffer didn't go
  // out of its bounds.
  uint8_t buffer[MBSize * 3];
  // Pre-fill the buffer with a known pattern, so we can later see what changed.
  for (size_t i = 0; i < MBSize * 3; ++i) {
    buffer[i] = uint8_t('A' + i);
  }
  MB mbByBuffer(&buffer[MBSize], MakePowerOfTwo32<MBSize>());
  TestModuloBuffer(mbByBuffer, MBSize);

  // Check that only the provided stack-based sub-buffer was modified.
  uint32_t changed = 0;
  for (size_t i = MBSize; i < MBSize * 2; ++i) {
    changed += (buffer[i] == uint8_t('A' + i)) ? 0 : 1;
  }
  // Expect at least 75% changes.
  MOZ_RELEASE_ASSERT(changed >= MBSize * 6 / 8);

  // Everything around the sub-buffer should be unchanged.
  for (size_t i = 0; i < MBSize; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }
  for (size_t i = MBSize * 2; i < MBSize * 3; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }

  // Check that move-construction is allowed. This verifies that we do not
  // crash from a double free, when `mbByBuffer` and `mbByStolenBuffer` are both
  // destroyed at the end of this function.
  MB mbByStolenBuffer = std::move(mbByBuffer);
  TestModuloBuffer(mbByStolenBuffer, MBSize);

  // Check that only the provided stack-based sub-buffer was modified.
  changed = 0;
  for (size_t i = MBSize; i < MBSize * 2; ++i) {
    changed += (buffer[i] == uint8_t('A' + i)) ? 0 : 1;
  }
  // Expect at least 75% changes.
  MOZ_RELEASE_ASSERT(changed >= MBSize * 6 / 8);

  // Everything around the sub-buffer should be unchanged.
  for (size_t i = 0; i < MBSize; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }
  for (size_t i = MBSize * 2; i < MBSize * 3; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }

  // This test function does a `ReadInto` as directed, and checks that the
  // result is the same as if the copy had been done manually byte-by-byte.
  // `TestReadInto(3, 7, 2)` copies from index 3 to index 7, 2 bytes long.
  // Return the output string (from `ReadInto`) for external checks.
  auto TestReadInto = [](MB::Index aReadFrom, MB::Index aWriteTo,
                         MB::Length aBytes) {
    constexpr uint32_t TRISize = 16;

    // Prepare an input buffer, all different elements.
    uint8_t input[TRISize + 1] = "ABCDEFGHIJKLMNOP";
    const MB mbInput(input, MakePowerOfTwo32<TRISize>());

    // Prepare an output buffer, different from input.
    uint8_t output[TRISize + 1] = "abcdefghijklmnop";
    MB mbOutput(output, MakePowerOfTwo32<TRISize>());

    // Run ReadInto.
    auto writer = mbOutput.WriterAt(aWriteTo);
    mbInput.ReaderAt(aReadFrom).ReadInto(writer, aBytes);

    // Do the same operation manually.
    uint8_t outputCheck[TRISize + 1] = "abcdefghijklmnop";
    MB mbOutputCheck(outputCheck, MakePowerOfTwo32<TRISize>());
    auto readerCheck = mbInput.ReaderAt(aReadFrom);
    auto writerCheck = mbOutputCheck.WriterAt(aWriteTo);
    for (MB::Length i = 0; i < aBytes; ++i) {
      *writerCheck++ = *readerCheck++;
    }

    // Compare the two outputs.
    for (uint32_t i = 0; i < TRISize; ++i) {
#  ifdef TEST_MODULOBUFFER_FAILURE_DEBUG
      // Only used when debugging failures.
      if (output[i] != outputCheck[i]) {
        printf(
            "*** from=%u to=%u bytes=%u i=%u\ninput:  '%s'\noutput: "
            "'%s'\ncheck:  '%s'\n",
            unsigned(aReadFrom), unsigned(aWriteTo), unsigned(aBytes),
            unsigned(i), input, output, outputCheck);
      }
#  endif
      MOZ_RELEASE_ASSERT(output[i] == outputCheck[i]);
    }

#  ifdef TEST_MODULOBUFFER_HELPER
    // Only used when adding more tests.
    printf("*** from=%u to=%u bytes=%u output: %s\n", unsigned(aReadFrom),
           unsigned(aWriteTo), unsigned(aBytes), output);
#  endif

    return std::string(reinterpret_cast<const char*>(output));
  };

  // A few manual checks:
  constexpr uint32_t TRISize = 16;
  MOZ_RELEASE_ASSERT(TestReadInto(0, 0, 0) == "abcdefghijklmnop");
  MOZ_RELEASE_ASSERT(TestReadInto(0, 0, TRISize) == "ABCDEFGHIJKLMNOP");
  MOZ_RELEASE_ASSERT(TestReadInto(0, 5, TRISize) == "LMNOPABCDEFGHIJK");
  MOZ_RELEASE_ASSERT(TestReadInto(5, 0, TRISize) == "FGHIJKLMNOPABCDE");

  // Test everything! (16^3 = 4096, not too much.)
  for (MB::Index r = 0; r < TRISize; ++r) {
    for (MB::Index w = 0; w < TRISize; ++w) {
      for (MB::Length len = 0; len < TRISize; ++len) {
        TestReadInto(r, w, len);
      }
    }
  }

  printf("TestModuloBuffer done\n");
}

void TestBlocksRingBufferAPI() {
  printf("TestBlocksRingBufferAPI...\n");

  // Create a 16-byte buffer, enough to store up to 3 entries (1 byte size + 4
  // bytes uint64_t).
  constexpr uint32_t MBSize = 16;
  uint8_t buffer[MBSize * 3];
  for (size_t i = 0; i < MBSize * 3; ++i) {
    buffer[i] = uint8_t('A' + i);
  }

  // Start a temporary block to constrain buffer lifetime.
  {
    BlocksRingBuffer rb(BlocksRingBuffer::ThreadSafety::WithMutex,
                        &buffer[MBSize], MakePowerOfTwo32<MBSize>());

#  define VERIFY_START_END_PUSHED_CLEARED(aStart, aEnd, aPushed, aCleared)  \
    {                                                                       \
      BlocksRingBuffer::State state = rb.GetState();                        \
      MOZ_RELEASE_ASSERT(state.mRangeStart.ConvertToProfileBufferIndex() == \
                         (aStart));                                         \
      MOZ_RELEASE_ASSERT(state.mRangeEnd.ConvertToProfileBufferIndex() ==   \
                         (aEnd));                                           \
      MOZ_RELEASE_ASSERT(state.mPushedBlockCount == (aPushed));             \
      MOZ_RELEASE_ASSERT(state.mClearedBlockCount == (aCleared));           \
    }

    // All entries will contain one 32-bit number. The resulting blocks will
    // have the following structure:
    // - 1 byte for the LEB128 size of 4
    // - 4 bytes for the number.
    // E.g., if we have entries with `123` and `456`:
    //   .-- Index 0 reserved for empty ProfileBufferBlockIndex, nothing there.
    //   | .-- first readable block at index 1
    //   | |.-- first block at index 1
    //   | ||.-- 1 byte for the entry size, which is `4` (32 bits)
    //   | |||  .-- entry starts at index 2, contains 32-bit int
    //   | |||  |             .-- entry and block finish *after* index 5 (so 6)
    //   | |||  |             | .-- second block starts at index 6
    //   | |||  |             | |         etc.
    //   | |||  |             | |                  .-- End readable blocks: 11
    //   v vvv  v             v V                  v
    //   0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15
    //   - S[4 |   int(123)   ] [4 |   int(456)   ]E

    // Empty buffer to start with.
    // Start&end indices still at 1 (0 is reserved for the default
    // ProfileBufferBlockIndex{} that cannot point at a valid entry), nothing
    // cleared.
    VERIFY_START_END_PUSHED_CLEARED(1, 1, 0, 0);

    // Default ProfileBufferBlockIndex.
    ProfileBufferBlockIndex bi0;
    if (bi0) {
      MOZ_RELEASE_ASSERT(false,
                         "if (ProfileBufferBlockIndex{}) should fail test");
    }
    if (!bi0) {
    } else {
      MOZ_RELEASE_ASSERT(false,
                         "if (!ProfileBufferBlockIndex{}) should succeed test");
    }
    MOZ_RELEASE_ASSERT(!bi0);
    MOZ_RELEASE_ASSERT(bi0 == bi0);
    MOZ_RELEASE_ASSERT(bi0 <= bi0);
    MOZ_RELEASE_ASSERT(bi0 >= bi0);
    MOZ_RELEASE_ASSERT(!(bi0 != bi0));
    MOZ_RELEASE_ASSERT(!(bi0 < bi0));
    MOZ_RELEASE_ASSERT(!(bi0 > bi0));

    // Default ProfileBufferBlockIndex can be used, but returns no valid entry.
    rb.ReadAt(bi0, [](Maybe<ProfileBufferEntryReader>&& aMaybeReader) {
      MOZ_RELEASE_ASSERT(aMaybeReader.isNothing());
    });

    // Push `1` directly.
    MOZ_RELEASE_ASSERT(
        rb.PutObject(uint32_t(1)).ConvertToProfileBufferIndex() == 1);
    //   0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15
    //   - S[4 |    int(1)    ]E
    VERIFY_START_END_PUSHED_CLEARED(1, 6, 1, 0);

    // Push `2` through ReserveAndPut, check output ProfileBufferBlockIndex.
    auto bi2 = rb.ReserveAndPut([]() { return sizeof(uint32_t); },
                                [](Maybe<ProfileBufferEntryWriter>& aEW) {
                                  MOZ_RELEASE_ASSERT(aEW.isSome());
                                  aEW->WriteObject(uint32_t(2));
                                  return aEW->CurrentBlockIndex();
                                });
    static_assert(std::is_same<decltype(bi2), ProfileBufferBlockIndex>::value,
                  "All index-returning functions should return a "
                  "ProfileBufferBlockIndex");
    MOZ_RELEASE_ASSERT(bi2.ConvertToProfileBufferIndex() == 6);
    //   0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15
    //   - S[4 |    int(1)    ] [4 |    int(2)    ]E
    VERIFY_START_END_PUSHED_CLEARED(1, 11, 2, 0);

    // Check single entry at bi2, store next block index.
    auto i2Next =
        rb.ReadAt(bi2, [bi2](Maybe<ProfileBufferEntryReader>&& aMaybeReader) {
          MOZ_RELEASE_ASSERT(aMaybeReader.isSome());
          MOZ_RELEASE_ASSERT(aMaybeReader->CurrentBlockIndex() == bi2);
          MOZ_RELEASE_ASSERT(aMaybeReader->NextBlockIndex() == nullptr);
          size_t entrySize = aMaybeReader->RemainingBytes();
          MOZ_RELEASE_ASSERT(aMaybeReader->ReadObject<uint32_t>() == 2);
          // The next block index is after this block, which is made of the
          // entry size (coded as ULEB128) followed by the entry itself.
          return bi2.ConvertToProfileBufferIndex() + ULEB128Size(entrySize) +
                 entrySize;
        });
    auto bi2Next = rb.GetState().mRangeEnd;
    MOZ_RELEASE_ASSERT(bi2Next.ConvertToProfileBufferIndex() == i2Next);
    // bi2Next is at the end, nothing to read.
    rb.ReadAt(bi2Next, [](Maybe<ProfileBufferEntryReader>&& aMaybeReader) {
      MOZ_RELEASE_ASSERT(aMaybeReader.isNothing());
    });

    // ProfileBufferBlockIndex tests.
    if (bi2) {
    } else {
      MOZ_RELEASE_ASSERT(
          false,
          "if (non-default-ProfileBufferBlockIndex) should succeed test");
    }
    if (!bi2) {
      MOZ_RELEASE_ASSERT(
          false, "if (!non-default-ProfileBufferBlockIndex) should fail test");
    }

    MOZ_RELEASE_ASSERT(!!bi2);
    MOZ_RELEASE_ASSERT(bi2 == bi2);
    MOZ_RELEASE_ASSERT(bi2 <= bi2);
    MOZ_RELEASE_ASSERT(bi2 >= bi2);
    MOZ_RELEASE_ASSERT(!(bi2 != bi2));
    MOZ_RELEASE_ASSERT(!(bi2 < bi2));
    MOZ_RELEASE_ASSERT(!(bi2 > bi2));

    MOZ_RELEASE_ASSERT(bi0 != bi2);
    MOZ_RELEASE_ASSERT(bi0 < bi2);
    MOZ_RELEASE_ASSERT(bi0 <= bi2);
    MOZ_RELEASE_ASSERT(!(bi0 == bi2));
    MOZ_RELEASE_ASSERT(!(bi0 > bi2));
    MOZ_RELEASE_ASSERT(!(bi0 >= bi2));

    MOZ_RELEASE_ASSERT(bi2 != bi0);
    MOZ_RELEASE_ASSERT(bi2 > bi0);
    MOZ_RELEASE_ASSERT(bi2 >= bi0);
    MOZ_RELEASE_ASSERT(!(bi2 == bi0));
    MOZ_RELEASE_ASSERT(!(bi2 < bi0));
    MOZ_RELEASE_ASSERT(!(bi2 <= bi0));

    MOZ_RELEASE_ASSERT(bi2 != bi2Next);
    MOZ_RELEASE_ASSERT(bi2 < bi2Next);
    MOZ_RELEASE_ASSERT(bi2 <= bi2Next);
    MOZ_RELEASE_ASSERT(!(bi2 == bi2Next));
    MOZ_RELEASE_ASSERT(!(bi2 > bi2Next));
    MOZ_RELEASE_ASSERT(!(bi2 >= bi2Next));

    MOZ_RELEASE_ASSERT(bi2Next != bi2);
    MOZ_RELEASE_ASSERT(bi2Next > bi2);
    MOZ_RELEASE_ASSERT(bi2Next >= bi2);
    MOZ_RELEASE_ASSERT(!(bi2Next == bi2));
    MOZ_RELEASE_ASSERT(!(bi2Next < bi2));
    MOZ_RELEASE_ASSERT(!(bi2Next <= bi2));

    // Push `3` through Put, check writer output
    // is returned to the initial caller.
    auto put3 =
        rb.Put(sizeof(uint32_t), [&](Maybe<ProfileBufferEntryWriter>& aEW) {
          MOZ_RELEASE_ASSERT(aEW.isSome());
          aEW->WriteObject(uint32_t(3));
          MOZ_RELEASE_ASSERT(aEW->CurrentBlockIndex() == bi2Next);
          return float(aEW->CurrentBlockIndex().ConvertToProfileBufferIndex());
        });
    static_assert(std::is_same<decltype(put3), float>::value,
                  "Expect float as returned by callback.");
    MOZ_RELEASE_ASSERT(put3 == 11.0);
    //   0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15 (16)
    //   - S[4 |    int(1)    ] [4 |    int(2)    ] [4 |    int(3)    ]E
    VERIFY_START_END_PUSHED_CLEARED(1, 16, 3, 0);

    // Re-Read single entry at bi2, it should now have a next entry.
    rb.ReadAt(bi2, [&](Maybe<ProfileBufferEntryReader>&& aMaybeReader) {
      MOZ_RELEASE_ASSERT(aMaybeReader.isSome());
      MOZ_RELEASE_ASSERT(aMaybeReader->CurrentBlockIndex() == bi2);
      MOZ_RELEASE_ASSERT(aMaybeReader->ReadObject<uint32_t>() == 2);
      MOZ_RELEASE_ASSERT(aMaybeReader->NextBlockIndex() == bi2Next);
    });

    // Check that we have `1` to `3`.
    uint32_t count = 0;
    rb.ReadEach([&](ProfileBufferEntryReader& aReader) {
      MOZ_RELEASE_ASSERT(aReader.ReadObject<uint32_t>() == ++count);
    });
    MOZ_RELEASE_ASSERT(count == 3);

    // Push `4`, store its ProfileBufferBlockIndex for later.
    // This will wrap around, and clear the first entry.
    ProfileBufferBlockIndex bi4 = rb.PutObject(uint32_t(4));
    // Before:
    //   0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15 (16)
    //   - S[4 |    int(1)    ] [4 |    int(2)    ] [4 |    int(3)    ]E
    // 1. First entry cleared:
    //   0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15 (16)
    //   -   ?   ?   ?   ?   ? S[4 |    int(2)    ] [4 |    int(3)    ]E
    // 2. New entry starts at 15 and wraps around: (shown on separate line)
    //   0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15 (16)
    //   -   ?   ?   ?   ?   ? S[4 |    int(2)    ] [4 |    int(3)    ]
    //  16  17  18  19  20  21  ...
    //  [4 |    int(4)    ]E
    // (collapsed)
    //  16  17  18  19  20  21   6   7   8   9  10  11  12  13  14  15 (16)
    //  [4 |    int(4)    ]E ? S[4 |    int(2)    ] [4 |    int(3)    ]
    VERIFY_START_END_PUSHED_CLEARED(6, 21, 4, 1);

    // Check that we have `2` to `4`.
    count = 1;
    rb.ReadEach([&](ProfileBufferEntryReader& aReader) {
      MOZ_RELEASE_ASSERT(aReader.ReadObject<uint32_t>() == ++count);
    });
    MOZ_RELEASE_ASSERT(count == 4);

    // Push 5 through Put, no returns.
    // This will clear the second entry.
    // Check that the EntryWriter can access bi4 but not bi2.
    auto bi5 =
        rb.Put(sizeof(uint32_t), [&](Maybe<ProfileBufferEntryWriter>& aEW) {
          MOZ_RELEASE_ASSERT(aEW.isSome());
          aEW->WriteObject(uint32_t(5));
          return aEW->CurrentBlockIndex();
        });
    auto bi6 = rb.GetState().mRangeEnd;
    //  16  17  18  19  20  21  22  23  24  25  26  11  12  13  14  15 (16)
    //  [4 |    int(4)    ] [4 |    int(5)    ]E ? S[4 |    int(3)    ]
    VERIFY_START_END_PUSHED_CLEARED(11, 26, 5, 2);

    // Read single entry at bi2, should now gracefully fail.
    rb.ReadAt(bi2, [](Maybe<ProfileBufferEntryReader>&& aMaybeReader) {
      MOZ_RELEASE_ASSERT(aMaybeReader.isNothing());
    });

    // Read single entry at bi5.
    rb.ReadAt(bi5, [](Maybe<ProfileBufferEntryReader>&& aMaybeReader) {
      MOZ_RELEASE_ASSERT(aMaybeReader.isSome());
      MOZ_RELEASE_ASSERT(aMaybeReader->ReadObject<uint32_t>() == 5);
    });

    rb.Read([&](BlocksRingBuffer::Reader* aReader) {
      MOZ_RELEASE_ASSERT(!!aReader);
      // begin() and end() should be at the range edges (verified above).
      MOZ_RELEASE_ASSERT(
          aReader->begin().CurrentBlockIndex().ConvertToProfileBufferIndex() ==
          11);
      MOZ_RELEASE_ASSERT(
          aReader->end().CurrentBlockIndex().ConvertToProfileBufferIndex() ==
          26);
      // Null ProfileBufferBlockIndex clamped to the beginning.
      MOZ_RELEASE_ASSERT(aReader->At(bi0) == aReader->begin());
      // Cleared block index clamped to the beginning.
      MOZ_RELEASE_ASSERT(aReader->At(bi2) == aReader->begin());
      // At(begin) same as begin().
      MOZ_RELEASE_ASSERT(aReader->At(aReader->begin().CurrentBlockIndex()) ==
                         aReader->begin());
      // bi5 at expected position.
      MOZ_RELEASE_ASSERT(
          aReader->At(bi5).CurrentBlockIndex().ConvertToProfileBufferIndex() ==
          21);
      // bi6 at expected position at the end.
      MOZ_RELEASE_ASSERT(aReader->At(bi6) == aReader->end());
      // At(end) same as end().
      MOZ_RELEASE_ASSERT(aReader->At(aReader->end().CurrentBlockIndex()) ==
                         aReader->end());
    });

    // Check that we have `3` to `5`.
    count = 2;
    rb.ReadEach([&](ProfileBufferEntryReader& aReader) {
      MOZ_RELEASE_ASSERT(aReader.ReadObject<uint32_t>() == ++count);
    });
    MOZ_RELEASE_ASSERT(count == 5);

    // Clear everything before `4`, this should clear `3`.
    rb.ClearBefore(bi4);
    //  16  17  18  19  20  21  22  23  24  25  26  11  12  13  14  15
    // S[4 |    int(4)    ] [4 |    int(5)    ]E ?   ?   ?   ?   ?   ?
    VERIFY_START_END_PUSHED_CLEARED(16, 26, 5, 3);

    // Check that we have `4` to `5`.
    count = 3;
    rb.ReadEach([&](ProfileBufferEntryReader& aReader) {
      MOZ_RELEASE_ASSERT(aReader.ReadObject<uint32_t>() == ++count);
    });
    MOZ_RELEASE_ASSERT(count == 5);

    // Clear everything before `4` again, nothing to clear.
    rb.ClearBefore(bi4);
    VERIFY_START_END_PUSHED_CLEARED(16, 26, 5, 3);

    // Clear everything, this should clear `4` and `5`, and bring the start
    // index where the end index currently is.
    rb.ClearBefore(bi6);
    //  16  17  18  19  20  21  22  23  24  25  26  11  12  13  14  15
    //   ?   ?   ?   ?   ?   ?   ?   ?   ?   ? SE?   ?   ?   ?   ?   ?
    VERIFY_START_END_PUSHED_CLEARED(26, 26, 5, 5);

    // Check that we have nothing to read.
    rb.ReadEach([&](auto&&) { MOZ_RELEASE_ASSERT(false); });

    // Read single entry at bi5, should now gracefully fail.
    rb.ReadAt(bi5, [](Maybe<ProfileBufferEntryReader>&& aMaybeReader) {
      MOZ_RELEASE_ASSERT(aMaybeReader.isNothing());
    });

    // Clear everything before now-cleared `4`, nothing to clear.
    rb.ClearBefore(bi4);
    VERIFY_START_END_PUSHED_CLEARED(26, 26, 5, 5);

    // Push `6` directly.
    MOZ_RELEASE_ASSERT(rb.PutObject(uint32_t(6)) == bi6);
    //  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
    //   ?   ?   ?   ?   ?   ?   ?   ?   ?   ? S[4 |    int(6)    ]E ?
    VERIFY_START_END_PUSHED_CLEARED(26, 31, 6, 5);

    {
      // Create a 2nd buffer and fill it with `7` and `8`.
      uint8_t buffer2[MBSize];
      BlocksRingBuffer rb2(BlocksRingBuffer::ThreadSafety::WithoutMutex,
                           buffer2, MakePowerOfTwo32<MBSize>());
      rb2.PutObject(uint32_t(7));
      rb2.PutObject(uint32_t(8));
      // Main buffer shouldn't have changed.
      VERIFY_START_END_PUSHED_CLEARED(26, 31, 6, 5);

      // Append contents of rb2 to rb, this should end up being the same as
      // pushing the two numbers.
      rb.AppendContents(rb2);
      //  32  33  34  35  36  37  38  39  40  41  26  27  28  29  30  31
      //      int(7)    ] [4 |    int(8)    ]E ? S[4 |    int(6)    ] [4 |
      VERIFY_START_END_PUSHED_CLEARED(26, 41, 8, 5);

      // Append contents of rb2 to rb again, to verify that rb2 was not modified
      // above. This should clear `6` and the first `7`.
      rb.AppendContents(rb2);
      //  48  49  50  51  36  37  38  39  40  41  42  43  44  45  46  47
      //  int(8)    ]E ? S[4 |    int(8)    ] [4 |    int(7)    ] [4 |
      VERIFY_START_END_PUSHED_CLEARED(36, 51, 10, 7);

      // End of block where rb2 lives, to verify that it is not needed anymore
      // for its copied values to survive in rb.
    }
    VERIFY_START_END_PUSHED_CLEARED(36, 51, 10, 7);

    // bi6 should now have been cleared.
    rb.ReadAt(bi6, [](Maybe<ProfileBufferEntryReader>&& aMaybeReader) {
      MOZ_RELEASE_ASSERT(aMaybeReader.isNothing());
    });

    // Check that we have `8`, `7`, `8`.
    count = 0;
    uint32_t expected[3] = {8, 7, 8};
    rb.ReadEach([&](ProfileBufferEntryReader& aReader) {
      MOZ_RELEASE_ASSERT(count < 3);
      MOZ_RELEASE_ASSERT(aReader.ReadObject<uint32_t>() == expected[count++]);
    });
    MOZ_RELEASE_ASSERT(count == 3);

    // End of block where rb lives, BlocksRingBuffer destructor should call
    // entry destructor for remaining entries.
  }

  // Check that only the provided stack-based sub-buffer was modified.
  uint32_t changed = 0;
  for (size_t i = MBSize; i < MBSize * 2; ++i) {
    changed += (buffer[i] == uint8_t('A' + i)) ? 0 : 1;
  }
  // Expect at least 75% changes.
  MOZ_RELEASE_ASSERT(changed >= MBSize * 6 / 8);

  // Everything around the sub-buffer should be unchanged.
  for (size_t i = 0; i < MBSize; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }
  for (size_t i = MBSize * 2; i < MBSize * 3; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }

  printf("TestBlocksRingBufferAPI done\n");
}

void TestBlocksRingBufferUnderlyingBufferChanges() {
  printf("TestBlocksRingBufferUnderlyingBufferChanges...\n");

  // Out-of-session BlocksRingBuffer to start with.
  BlocksRingBuffer rb(BlocksRingBuffer::ThreadSafety::WithMutex);

  // Block index to read at. Initially "null", but may be changed below.
  ProfileBufferBlockIndex bi;

  // Test all rb APIs when rb is out-of-session and therefore doesn't have an
  // underlying buffer.
  auto testOutOfSession = [&]() {
    MOZ_RELEASE_ASSERT(rb.BufferLength().isNothing());
    BlocksRingBuffer::State state = rb.GetState();
    // When out-of-session, range start and ends are the same, and there are no
    // pushed&cleared blocks.
    MOZ_RELEASE_ASSERT(state.mRangeStart == state.mRangeEnd);
    MOZ_RELEASE_ASSERT(state.mPushedBlockCount == 0);
    MOZ_RELEASE_ASSERT(state.mClearedBlockCount == 0);
    // `Put()` functions run the callback with `Nothing`.
    int32_t ran = 0;
    rb.Put(1, [&](Maybe<ProfileBufferEntryWriter>& aMaybeEntryWriter) {
      MOZ_RELEASE_ASSERT(aMaybeEntryWriter.isNothing());
      ++ran;
    });
    MOZ_RELEASE_ASSERT(ran == 1);
    // `PutFrom` won't do anything, and returns the null
    // ProfileBufferBlockIndex.
    MOZ_RELEASE_ASSERT(rb.PutFrom(&ran, sizeof(ran)) ==
                       ProfileBufferBlockIndex{});
    MOZ_RELEASE_ASSERT(rb.PutObject(ran) == ProfileBufferBlockIndex{});
    // `Read()` functions run the callback with `Nothing`.
    ran = 0;
    rb.Read([&](BlocksRingBuffer::Reader* aReader) {
      MOZ_RELEASE_ASSERT(!aReader);
      ++ran;
    });
    MOZ_RELEASE_ASSERT(ran == 1);
    ran = 0;
    rb.ReadAt(ProfileBufferBlockIndex{},
              [&](Maybe<ProfileBufferEntryReader>&& aMaybeEntryReader) {
                MOZ_RELEASE_ASSERT(aMaybeEntryReader.isNothing());
                ++ran;
              });
    MOZ_RELEASE_ASSERT(ran == 1);
    ran = 0;
    rb.ReadAt(bi, [&](Maybe<ProfileBufferEntryReader>&& aMaybeEntryReader) {
      MOZ_RELEASE_ASSERT(aMaybeEntryReader.isNothing());
      ++ran;
    });
    MOZ_RELEASE_ASSERT(ran == 1);
    // `ReadEach` shouldn't run the callback (nothing to read).
    rb.ReadEach([](auto&&) { MOZ_RELEASE_ASSERT(false); });
  };

  // As `testOutOfSession()` attempts to modify the buffer, we run it twice to
  // make sure one run doesn't influence the next one.
  testOutOfSession();
  testOutOfSession();

  rb.ClearBefore(bi);
  testOutOfSession();
  testOutOfSession();

  rb.Clear();
  testOutOfSession();
  testOutOfSession();

  rb.Reset();
  testOutOfSession();
  testOutOfSession();

  constexpr uint32_t MBSize = 32;

  rb.Set(MakePowerOfTwo<BlocksRingBuffer::Length, MBSize>());

  constexpr bool EMPTY = true;
  constexpr bool NOT_EMPTY = false;
  // Test all rb APIs when rb has an underlying buffer.
  auto testInSession = [&](bool aExpectEmpty) {
    MOZ_RELEASE_ASSERT(rb.BufferLength().isSome());
    BlocksRingBuffer::State state = rb.GetState();
    if (aExpectEmpty) {
      MOZ_RELEASE_ASSERT(state.mRangeStart == state.mRangeEnd);
      MOZ_RELEASE_ASSERT(state.mPushedBlockCount == 0);
      MOZ_RELEASE_ASSERT(state.mClearedBlockCount == 0);
    } else {
      MOZ_RELEASE_ASSERT(state.mRangeStart < state.mRangeEnd);
      MOZ_RELEASE_ASSERT(state.mPushedBlockCount > 0);
      MOZ_RELEASE_ASSERT(state.mClearedBlockCount <= state.mPushedBlockCount);
    }
    int32_t ran = 0;
    // The following three `Put...` will write three int32_t of value 1.
    bi = rb.Put(sizeof(ran),
                [&](Maybe<ProfileBufferEntryWriter>& aMaybeEntryWriter) {
                  MOZ_RELEASE_ASSERT(aMaybeEntryWriter.isSome());
                  ++ran;
                  aMaybeEntryWriter->WriteObject(ran);
                  return aMaybeEntryWriter->CurrentBlockIndex();
                });
    MOZ_RELEASE_ASSERT(ran == 1);
    MOZ_RELEASE_ASSERT(rb.PutFrom(&ran, sizeof(ran)) !=
                       ProfileBufferBlockIndex{});
    MOZ_RELEASE_ASSERT(rb.PutObject(ran) != ProfileBufferBlockIndex{});
    ran = 0;
    rb.Read([&](BlocksRingBuffer::Reader* aReader) {
      MOZ_RELEASE_ASSERT(!!aReader);
      ++ran;
    });
    MOZ_RELEASE_ASSERT(ran == 1);
    ran = 0;
    rb.ReadEach([&](ProfileBufferEntryReader& aEntryReader) {
      MOZ_RELEASE_ASSERT(aEntryReader.RemainingBytes() == sizeof(ran));
      MOZ_RELEASE_ASSERT(aEntryReader.ReadObject<decltype(ran)>() == 1);
      ++ran;
    });
    MOZ_RELEASE_ASSERT(ran >= 3);
    ran = 0;
    rb.ReadAt(ProfileBufferBlockIndex{},
              [&](Maybe<ProfileBufferEntryReader>&& aMaybeEntryReader) {
                MOZ_RELEASE_ASSERT(aMaybeEntryReader.isNothing());
                ++ran;
              });
    MOZ_RELEASE_ASSERT(ran == 1);
    ran = 0;
    rb.ReadAt(bi, [&](Maybe<ProfileBufferEntryReader>&& aMaybeEntryReader) {
      MOZ_RELEASE_ASSERT(aMaybeEntryReader.isNothing() == !bi);
      ++ran;
    });
    MOZ_RELEASE_ASSERT(ran == 1);
  };

  testInSession(EMPTY);
  testInSession(NOT_EMPTY);

  rb.Set(MakePowerOfTwo<BlocksRingBuffer::Length, 32>());
  MOZ_RELEASE_ASSERT(rb.BufferLength().isSome());
  rb.ReadEach([](auto&&) { MOZ_RELEASE_ASSERT(false); });

  testInSession(EMPTY);
  testInSession(NOT_EMPTY);

  rb.Reset();
  testOutOfSession();
  testOutOfSession();

  uint8_t buffer[MBSize * 3];
  for (size_t i = 0; i < MBSize * 3; ++i) {
    buffer[i] = uint8_t('A' + i);
  }

  rb.Set(&buffer[MBSize], MakePowerOfTwo<BlocksRingBuffer::Length, MBSize>());
  MOZ_RELEASE_ASSERT(rb.BufferLength().isSome());
  rb.ReadEach([](auto&&) { MOZ_RELEASE_ASSERT(false); });

  testInSession(EMPTY);
  testInSession(NOT_EMPTY);

  rb.Reset();
  testOutOfSession();
  testOutOfSession();

  rb.Set(&buffer[MBSize], MakePowerOfTwo<BlocksRingBuffer::Length, MBSize>());
  MOZ_RELEASE_ASSERT(rb.BufferLength().isSome());
  rb.ReadEach([](auto&&) { MOZ_RELEASE_ASSERT(false); });

  testInSession(EMPTY);
  testInSession(NOT_EMPTY);

  // Remove the current underlying buffer, this should clear all entries.
  rb.Reset();

  // Check that only the provided stack-based sub-buffer was modified.
  uint32_t changed = 0;
  for (size_t i = MBSize; i < MBSize * 2; ++i) {
    changed += (buffer[i] == uint8_t('A' + i)) ? 0 : 1;
  }
  // Expect at least 75% changes.
  MOZ_RELEASE_ASSERT(changed >= MBSize * 6 / 8);

  // Everything around the sub-buffer should be unchanged.
  for (size_t i = 0; i < MBSize; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }
  for (size_t i = MBSize * 2; i < MBSize * 3; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }

  testOutOfSession();
  testOutOfSession();

  printf("TestBlocksRingBufferUnderlyingBufferChanges done\n");
}

void TestBlocksRingBufferThreading() {
  printf("TestBlocksRingBufferThreading...\n");

  constexpr uint32_t MBSize = 8192;
  uint8_t buffer[MBSize * 3];
  for (size_t i = 0; i < MBSize * 3; ++i) {
    buffer[i] = uint8_t('A' + i);
  }
  BlocksRingBuffer rb(BlocksRingBuffer::ThreadSafety::WithMutex,
                      &buffer[MBSize], MakePowerOfTwo32<MBSize>());

  // Start reader thread.
  std::atomic<bool> stopReader{false};
  std::thread reader([&]() {
    for (;;) {
      BlocksRingBuffer::State state = rb.GetState();
      printf(
          "Reader: range=%llu..%llu (%llu bytes) pushed=%llu cleared=%llu "
          "(alive=%llu)\n",
          static_cast<unsigned long long>(
              state.mRangeStart.ConvertToProfileBufferIndex()),
          static_cast<unsigned long long>(
              state.mRangeEnd.ConvertToProfileBufferIndex()),
          static_cast<unsigned long long>(
              state.mRangeEnd.ConvertToProfileBufferIndex()) -
              static_cast<unsigned long long>(
                  state.mRangeStart.ConvertToProfileBufferIndex()),
          static_cast<unsigned long long>(state.mPushedBlockCount),
          static_cast<unsigned long long>(state.mClearedBlockCount),
          static_cast<unsigned long long>(state.mPushedBlockCount -
                                          state.mClearedBlockCount));
      if (stopReader) {
        break;
      }
      ::SleepMilli(1);
    }
  });

  // Start writer threads.
  constexpr int ThreadCount = 32;
  std::thread threads[ThreadCount];
  for (int threadNo = 0; threadNo < ThreadCount; ++threadNo) {
    threads[threadNo] = std::thread(
        [&](int aThreadNo) {
          ::SleepMilli(1);
          constexpr int pushCount = 1024;
          for (int push = 0; push < pushCount; ++push) {
            // Reserve as many bytes as the thread number (but at least enough
            // to store an int), and write an increasing int.
            rb.Put(std::max(aThreadNo, int(sizeof(push))),
                   [&](Maybe<ProfileBufferEntryWriter>& aEW) {
                     MOZ_RELEASE_ASSERT(aEW.isSome());
                     aEW->WriteObject(aThreadNo * 1000000 + push);
                     *aEW += aEW->RemainingBytes();
                   });
          }
        },
        threadNo);
  }

  // Wait for all writer threads to die.
  for (auto&& thread : threads) {
    thread.join();
  }

  // Stop reader thread.
  stopReader = true;
  reader.join();

  // Check that only the provided stack-based sub-buffer was modified.
  uint32_t changed = 0;
  for (size_t i = MBSize; i < MBSize * 2; ++i) {
    changed += (buffer[i] == uint8_t('A' + i)) ? 0 : 1;
  }
  // Expect at least 75% changes.
  MOZ_RELEASE_ASSERT(changed >= MBSize * 6 / 8);

  // Everything around the sub-buffer should be unchanged.
  for (size_t i = 0; i < MBSize; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }
  for (size_t i = MBSize * 2; i < MBSize * 3; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }

  printf("TestBlocksRingBufferThreading done\n");
}

void TestBlocksRingBufferSerialization() {
  printf("TestBlocksRingBufferSerialization...\n");

  constexpr uint32_t MBSize = 64;
  uint8_t buffer[MBSize * 3];
  for (size_t i = 0; i < MBSize * 3; ++i) {
    buffer[i] = uint8_t('A' + i);
  }
  BlocksRingBuffer rb(BlocksRingBuffer::ThreadSafety::WithMutex,
                      &buffer[MBSize], MakePowerOfTwo32<MBSize>());

  // Will expect literal string to always have the same address.
#  define THE_ANSWER "The answer is "
  const char* theAnswer = THE_ANSWER;

  rb.PutObjects('0', WrapProfileBufferLiteralCStringPointer(THE_ANSWER), 42,
                std::string(" but pi="), 3.14);
  rb.ReadEach([&](ProfileBufferEntryReader& aER) {
    char c0;
    const char* answer;
    int integer;
    std::string str;
    double pi;
    aER.ReadIntoObjects(c0, answer, integer, str, pi);
    MOZ_RELEASE_ASSERT(c0 == '0');
    MOZ_RELEASE_ASSERT(answer == theAnswer);
    MOZ_RELEASE_ASSERT(integer == 42);
    MOZ_RELEASE_ASSERT(str == " but pi=");
    MOZ_RELEASE_ASSERT(pi == 3.14);
  });
  rb.ReadEach([&](ProfileBufferEntryReader& aER) {
    char c0 = aER.ReadObject<char>();
    MOZ_RELEASE_ASSERT(c0 == '0');
    const char* answer = aER.ReadObject<const char*>();
    MOZ_RELEASE_ASSERT(answer == theAnswer);
    int integer = aER.ReadObject<int>();
    MOZ_RELEASE_ASSERT(integer == 42);
    std::string str = aER.ReadObject<std::string>();
    MOZ_RELEASE_ASSERT(str == " but pi=");
    double pi = aER.ReadObject<double>();
    MOZ_RELEASE_ASSERT(pi == 3.14);
  });

  rb.Clear();
  // Write an int and store its ProfileBufferBlockIndex.
  ProfileBufferBlockIndex blockIndex = rb.PutObject(123);
  // It should be non-0.
  MOZ_RELEASE_ASSERT(blockIndex != ProfileBufferBlockIndex{});
  // Write that ProfileBufferBlockIndex.
  rb.PutObject(blockIndex);
  rb.Read([&](BlocksRingBuffer::Reader* aR) {
    BlocksRingBuffer::BlockIterator it = aR->begin();
    const BlocksRingBuffer::BlockIterator itEnd = aR->end();
    MOZ_RELEASE_ASSERT(it != itEnd);
    MOZ_RELEASE_ASSERT((*it).ReadObject<int>() == 123);
    ++it;
    MOZ_RELEASE_ASSERT(it != itEnd);
    MOZ_RELEASE_ASSERT((*it).ReadObject<ProfileBufferBlockIndex>() ==
                       blockIndex);
    ++it;
    MOZ_RELEASE_ASSERT(it == itEnd);
  });

  rb.Clear();
  rb.PutObjects(
      std::make_tuple('0', WrapProfileBufferLiteralCStringPointer(THE_ANSWER),
                      42, std::string(" but pi="), 3.14));
  rb.ReadEach([&](ProfileBufferEntryReader& aER) {
    MOZ_RELEASE_ASSERT(aER.ReadObject<char>() == '0');
    MOZ_RELEASE_ASSERT(aER.ReadObject<const char*>() == theAnswer);
    MOZ_RELEASE_ASSERT(aER.ReadObject<int>() == 42);
    MOZ_RELEASE_ASSERT(aER.ReadObject<std::string>() == " but pi=");
    MOZ_RELEASE_ASSERT(aER.ReadObject<double>() == 3.14);
  });

  rb.Clear();
  rb.PutObjects(MakeTuple('0',
                          WrapProfileBufferLiteralCStringPointer(THE_ANSWER),
                          42, std::string(" but pi="), 3.14));
  rb.ReadEach([&](ProfileBufferEntryReader& aER) {
    MOZ_RELEASE_ASSERT(aER.ReadObject<char>() == '0');
    MOZ_RELEASE_ASSERT(aER.ReadObject<const char*>() == theAnswer);
    MOZ_RELEASE_ASSERT(aER.ReadObject<int>() == 42);
    MOZ_RELEASE_ASSERT(aER.ReadObject<std::string>() == " but pi=");
    MOZ_RELEASE_ASSERT(aER.ReadObject<double>() == 3.14);
  });

  rb.Clear();
  {
    UniqueFreePtr<char> ufps(strdup(THE_ANSWER));
    rb.PutObjects(ufps);
  }
  rb.ReadEach([&](ProfileBufferEntryReader& aER) {
    auto ufps = aER.ReadObject<UniqueFreePtr<char>>();
    MOZ_RELEASE_ASSERT(!!ufps);
    MOZ_RELEASE_ASSERT(std::string(THE_ANSWER) == ufps.get());
  });

  rb.Clear();
  int intArray[] = {1, 2, 3, 4, 5};
  rb.PutObjects(MakeSpan(intArray));
  rb.ReadEach([&](ProfileBufferEntryReader& aER) {
    int intArrayOut[sizeof(intArray) / sizeof(intArray[0])] = {0};
    auto outSpan = MakeSpan(intArrayOut);
    aER.ReadIntoObject(outSpan);
    for (size_t i = 0; i < sizeof(intArray) / sizeof(intArray[0]); ++i) {
      MOZ_RELEASE_ASSERT(intArrayOut[i] == intArray[i]);
    }
  });

  rb.Clear();
  rb.PutObjects(Maybe<int>(Nothing{}), Maybe<int>(Some(123)));
  rb.ReadEach([&](ProfileBufferEntryReader& aER) {
    Maybe<int> mi0, mi1;
    aER.ReadIntoObjects(mi0, mi1);
    MOZ_RELEASE_ASSERT(mi0.isNothing());
    MOZ_RELEASE_ASSERT(mi1.isSome());
    MOZ_RELEASE_ASSERT(*mi1 == 123);
  });

  rb.Clear();
  using V = Variant<int, double, int>;
  V v0(VariantIndex<0>{}, 123);
  V v1(3.14);
  V v2(VariantIndex<2>{}, 456);
  rb.PutObjects(v0, v1, v2);
  rb.ReadEach([&](ProfileBufferEntryReader& aER) {
    MOZ_RELEASE_ASSERT(aER.ReadObject<V>() == v0);
    MOZ_RELEASE_ASSERT(aER.ReadObject<V>() == v1);
    MOZ_RELEASE_ASSERT(aER.ReadObject<V>() == v2);
  });

  // 2nd BlocksRingBuffer to contain the 1st one. It has be be more than twice
  // the size.
  constexpr uint32_t MBSize2 = MBSize * 4;
  uint8_t buffer2[MBSize2 * 3];
  for (size_t i = 0; i < MBSize2 * 3; ++i) {
    buffer2[i] = uint8_t('B' + i);
  }
  BlocksRingBuffer rb2(BlocksRingBuffer::ThreadSafety::WithoutMutex,
                       &buffer2[MBSize2], MakePowerOfTwo32<MBSize2>());
  rb2.PutObject(rb);

  // 3rd BlocksRingBuffer deserialized from the 2nd one.
  uint8_t buffer3[MBSize * 3];
  for (size_t i = 0; i < MBSize * 3; ++i) {
    buffer3[i] = uint8_t('C' + i);
  }
  BlocksRingBuffer rb3(BlocksRingBuffer::ThreadSafety::WithoutMutex,
                       &buffer3[MBSize], MakePowerOfTwo32<MBSize>());
  rb2.ReadEach([&](ProfileBufferEntryReader& aER) { aER.ReadIntoObject(rb3); });

  // And a 4th heap-allocated one.
  UniquePtr<BlocksRingBuffer> rb4up;
  rb2.ReadEach([&](ProfileBufferEntryReader& aER) {
    rb4up = aER.ReadObject<UniquePtr<BlocksRingBuffer>>();
  });
  MOZ_RELEASE_ASSERT(!!rb4up);

  // Clear 1st and 2nd BlocksRingBuffers, to ensure we have made a deep copy
  // into the 3rd&4th ones.
  rb.Clear();
  rb2.Clear();

  // And now the 3rd one should have the same contents as the 1st one had.
  rb3.ReadEach([&](ProfileBufferEntryReader& aER) {
    MOZ_RELEASE_ASSERT(aER.ReadObject<V>() == v0);
    MOZ_RELEASE_ASSERT(aER.ReadObject<V>() == v1);
    MOZ_RELEASE_ASSERT(aER.ReadObject<V>() == v2);
  });

  // And 4th.
  rb4up->ReadEach([&](ProfileBufferEntryReader& aER) {
    MOZ_RELEASE_ASSERT(aER.ReadObject<V>() == v0);
    MOZ_RELEASE_ASSERT(aER.ReadObject<V>() == v1);
    MOZ_RELEASE_ASSERT(aER.ReadObject<V>() == v2);
  });

  // In fact, the 3rd and 4th ones should have the same state, because they were
  // created the same way.
  MOZ_RELEASE_ASSERT(rb3.GetState().mRangeStart ==
                     rb4up->GetState().mRangeStart);
  MOZ_RELEASE_ASSERT(rb3.GetState().mRangeEnd == rb4up->GetState().mRangeEnd);
  MOZ_RELEASE_ASSERT(rb3.GetState().mPushedBlockCount ==
                     rb4up->GetState().mPushedBlockCount);
  MOZ_RELEASE_ASSERT(rb3.GetState().mClearedBlockCount ==
                     rb4up->GetState().mClearedBlockCount);

  // Check that only the provided stack-based sub-buffer was modified.
  uint32_t changed = 0;
  for (size_t i = MBSize; i < MBSize * 2; ++i) {
    changed += (buffer[i] == uint8_t('A' + i)) ? 0 : 1;
  }
  // Expect at least 75% changes.
  MOZ_RELEASE_ASSERT(changed >= MBSize * 6 / 8);

  // Everything around the sub-buffers should be unchanged.
  for (size_t i = 0; i < MBSize; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }
  for (size_t i = MBSize * 2; i < MBSize * 3; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }

  for (size_t i = 0; i < MBSize2; ++i) {
    MOZ_RELEASE_ASSERT(buffer2[i] == uint8_t('B' + i));
  }
  for (size_t i = MBSize2 * 2; i < MBSize2 * 3; ++i) {
    MOZ_RELEASE_ASSERT(buffer2[i] == uint8_t('B' + i));
  }

  for (size_t i = 0; i < MBSize; ++i) {
    MOZ_RELEASE_ASSERT(buffer3[i] == uint8_t('C' + i));
  }
  for (size_t i = MBSize * 2; i < MBSize * 3; ++i) {
    MOZ_RELEASE_ASSERT(buffer3[i] == uint8_t('C' + i));
  }

  printf("TestBlocksRingBufferSerialization done\n");
}

void TestProfilerDependencies() {
  TestPowerOfTwoMask();
  TestPowerOfTwo();
  TestLEB128();
  TestChunk();
  TestChunkManagerSingle();
  TestChunkManagerWithLocalLimit();
  TestControlledChunkManagerUpdate();
  TestControlledChunkManagerWithLocalLimit();
  TestChunkedBuffer();
  TestChunkedBufferSingle();
  TestModuloBuffer();
  TestBlocksRingBufferAPI();
  TestBlocksRingBufferUnderlyingBufferChanges();
  TestBlocksRingBufferThreading();
  TestBlocksRingBufferSerialization();
}

class BaseTestMarkerPayload : public baseprofiler::ProfilerMarkerPayload {
 public:
  explicit BaseTestMarkerPayload(int aData) : mData(aData) {}

  int GetData() const { return mData; }

  // Exploded DECL_BASE_STREAM_PAYLOAD, but without `MFBT_API`s.
  static UniquePtr<ProfilerMarkerPayload> Deserialize(
      ProfileBufferEntryReader& aEntryReader);
  ProfileBufferEntryWriter::Length TagAndSerializationBytes() const override;
  void SerializeTagAndPayload(
      ProfileBufferEntryWriter& aEntryWriter) const override;
  void StreamPayload(
      ::mozilla::baseprofiler::SpliceableJSONWriter& aWriter,
      const ::mozilla::TimeStamp& aProcessStartTime,
      ::mozilla::baseprofiler::UniqueStacks& aUniqueStacks) const override;

 private:
  BaseTestMarkerPayload(CommonProps&& aProps, int aData)
      : baseprofiler::ProfilerMarkerPayload(std::move(aProps)), mData(aData) {}

  int mData;
};

// static
UniquePtr<baseprofiler::ProfilerMarkerPayload>
BaseTestMarkerPayload::Deserialize(ProfileBufferEntryReader& aEntryReader) {
  CommonProps props = DeserializeCommonProps(aEntryReader);
  int data = aEntryReader.ReadObject<int>();
  return UniquePtr<baseprofiler::ProfilerMarkerPayload>(
      new BaseTestMarkerPayload(std::move(props), data));
}

ProfileBufferEntryWriter::Length
BaseTestMarkerPayload::TagAndSerializationBytes() const {
  return CommonPropsTagAndSerializationBytes() + sizeof(int);
}

void BaseTestMarkerPayload::SerializeTagAndPayload(
    ProfileBufferEntryWriter& aEntryWriter) const {
  static const DeserializerTag tag = TagForDeserializer(Deserialize);
  SerializeTagAndCommonProps(tag, aEntryWriter);
  aEntryWriter.WriteObject(mData);
}

void BaseTestMarkerPayload::StreamPayload(
    baseprofiler::SpliceableJSONWriter& aWriter,
    const TimeStamp& aProcessStartTime,
    baseprofiler::UniqueStacks& aUniqueStacks) const {
  aWriter.IntProperty("data", mData);
}

void TestProfilerMarkerSerialization() {
  printf("TestProfilerMarkerSerialization...\n");

  constexpr uint32_t MBSize = 256;
  uint8_t buffer[MBSize * 3];
  for (size_t i = 0; i < MBSize * 3; ++i) {
    buffer[i] = uint8_t('A' + i);
  }
  BlocksRingBuffer rb(BlocksRingBuffer::ThreadSafety::WithMutex,
                      &buffer[MBSize], MakePowerOfTwo32<MBSize>());

  constexpr int data = 42;
  {
    BaseTestMarkerPayload payload(data);
    rb.PutObject(
        static_cast<const baseprofiler::ProfilerMarkerPayload*>(&payload));
  }

  int read = 0;
  rb.ReadEach([&](ProfileBufferEntryReader& aER) {
    UniquePtr<baseprofiler::ProfilerMarkerPayload> payload =
        aER.ReadObject<UniquePtr<baseprofiler::ProfilerMarkerPayload>>();
    MOZ_RELEASE_ASSERT(!!payload);
    ++read;
    BaseTestMarkerPayload* testPayload =
        static_cast<BaseTestMarkerPayload*>(payload.get());
    MOZ_RELEASE_ASSERT(testPayload);
    MOZ_RELEASE_ASSERT(testPayload->GetData() == data);
  });
  MOZ_RELEASE_ASSERT(read == 1);

  // Everything around the sub-buffer should be unchanged.
  for (size_t i = 0; i < MBSize; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }
  for (size_t i = MBSize * 2; i < MBSize * 3; ++i) {
    MOZ_RELEASE_ASSERT(buffer[i] == uint8_t('A' + i));
  }

  printf("TestProfilerMarkerSerialization done\n");
}

// Increase the depth, to a maximum (to avoid too-deep recursion).
static constexpr size_t NextDepth(size_t aDepth) {
  constexpr size_t MAX_DEPTH = 128;
  return (aDepth < MAX_DEPTH) ? (aDepth + 1) : aDepth;
}

Atomic<bool, Relaxed> sStopFibonacci;

// Compute fibonacci the hard way (recursively: `f(n)=f(n-1)+f(n-2)`), and
// prevent inlining.
// The template parameter makes each depth be a separate function, to better
// distinguish them in the profiler output.
template <size_t DEPTH = 0>
MOZ_NEVER_INLINE unsigned long long Fibonacci(unsigned long long n) {
  AUTO_BASE_PROFILER_LABEL_DYNAMIC_STRING("fib", OTHER, std::to_string(DEPTH));
  if (n == 0) {
    return 0;
  }
  if (n == 1) {
    return 1;
  }
  if (DEPTH < 5 && sStopFibonacci) {
    return 1'000'000'000;
  }
  TimeStamp start = TimeStamp::NowUnfuzzed();
  static constexpr size_t MAX_MARKER_DEPTH = 10;
  unsigned long long f2 = Fibonacci<NextDepth(DEPTH)>(n - 2);
  if (DEPTH == 0) {
    BASE_PROFILER_ADD_MARKER("Half-way through Fibonacci", OTHER);
  }
  unsigned long long f1 = Fibonacci<NextDepth(DEPTH)>(n - 1);
  if (DEPTH < MAX_MARKER_DEPTH) {
    baseprofiler::profiler_add_text_marker(
        "fib", std::to_string(DEPTH),
        baseprofiler::ProfilingCategoryPair::OTHER, start,
        TimeStamp::NowUnfuzzed());
  }
  return f2 + f1;
}

void TestProfiler() {
  printf("TestProfiler starting -- pid: %d, tid: %d\n",
         baseprofiler::profiler_current_process_id(),
         baseprofiler::profiler_current_thread_id());
  // ::SleepMilli(10000);

  TestProfilerDependencies();

  TestProfilerMarkerSerialization();

  {
    printf("profiler_init()...\n");
    AUTO_BASE_PROFILER_INIT;

    MOZ_RELEASE_ASSERT(!baseprofiler::profiler_is_active());
    MOZ_RELEASE_ASSERT(!baseprofiler::profiler_thread_is_being_profiled());
    MOZ_RELEASE_ASSERT(!baseprofiler::profiler_thread_is_sleeping());

    printf("profiler_start()...\n");
    Vector<const char*> filters;
    // Profile all registered threads.
    MOZ_RELEASE_ASSERT(filters.append(""));
    const uint32_t features = baseprofiler::ProfilerFeature::Leaf |
                              baseprofiler::ProfilerFeature::StackWalk |
                              baseprofiler::ProfilerFeature::Threads;
    baseprofiler::profiler_start(baseprofiler::BASE_PROFILER_DEFAULT_ENTRIES,
                                 BASE_PROFILER_DEFAULT_INTERVAL, features,
                                 filters.begin(), filters.length());

    MOZ_RELEASE_ASSERT(baseprofiler::profiler_is_active());
    MOZ_RELEASE_ASSERT(baseprofiler::profiler_thread_is_being_profiled());
    MOZ_RELEASE_ASSERT(!baseprofiler::profiler_thread_is_sleeping());

    sStopFibonacci = false;

    std::thread threadFib([]() {
      AUTO_BASE_PROFILER_REGISTER_THREAD("fibonacci");
      SleepMilli(5);
      auto cause =
#  if defined(__linux__) || defined(__ANDROID__)
          // Currently disabled on these platforms, so just return a null.
          decltype(baseprofiler::profiler_get_backtrace()){};
#  else
          baseprofiler::profiler_get_backtrace();
#  endif
      AUTO_BASE_PROFILER_TEXT_MARKER_CAUSE("fibonacci", "First leaf call",
                                           OTHER, std::move(cause));
      static const unsigned long long fibStart = 37;
      printf("Fibonacci(%llu)...\n", fibStart);
      AUTO_BASE_PROFILER_LABEL("Label around Fibonacci", OTHER);
      unsigned long long f = Fibonacci(fibStart);
      printf("Fibonacci(%llu) = %llu\n", fibStart, f);
    });

    std::thread threadCancelFib([]() {
      AUTO_BASE_PROFILER_REGISTER_THREAD("fibonacci canceller");
      SleepMilli(5);
      AUTO_BASE_PROFILER_TEXT_MARKER_CAUSE("fibonacci", "Canceller", OTHER,
                                           nullptr);
      static const int waitMaxSeconds = 10;
      for (int i = 0; i < waitMaxSeconds; ++i) {
        if (sStopFibonacci) {
          AUTO_BASE_PROFILER_LABEL_DYNAMIC_STRING("fibCancel", OTHER,
                                                  std::to_string(i));
          return;
        }
        AUTO_BASE_PROFILER_THREAD_SLEEP;
        SleepMilli(1000);
      }
      AUTO_BASE_PROFILER_LABEL_DYNAMIC_STRING("fibCancel", OTHER,
                                              "Cancelling!");
      sStopFibonacci = true;
    });

    {
      AUTO_BASE_PROFILER_TEXT_MARKER_CAUSE(
          "main thread", "joining fibonacci thread", OTHER, nullptr);
      AUTO_BASE_PROFILER_THREAD_SLEEP;
      threadFib.join();
    }

    {
      AUTO_BASE_PROFILER_TEXT_MARKER_CAUSE(
          "main thread", "joining fibonacci-canceller thread", OTHER, nullptr);
      sStopFibonacci = true;
      AUTO_BASE_PROFILER_THREAD_SLEEP;
      threadCancelFib.join();
    }

    // Just making sure all payloads know how to (de)serialize and stream.
    baseprofiler::profiler_add_marker(
        "TracingMarkerPayload", baseprofiler::ProfilingCategoryPair::OTHER,
        baseprofiler::TracingMarkerPayload("category",
                                           baseprofiler::TRACING_EVENT));

    auto cause =
#  if defined(__linux__) || defined(__ANDROID__)
        // Currently disabled on these platforms, so just return a null.
        decltype(baseprofiler::profiler_get_backtrace()){};
#  else
        baseprofiler::profiler_get_backtrace();
#  endif
    baseprofiler::profiler_add_marker(
        "FileIOMarkerPayload", baseprofiler::ProfilingCategoryPair::OTHER,
        baseprofiler::FileIOMarkerPayload(
            "operation", "source", "filename", TimeStamp::NowUnfuzzed(),
            TimeStamp::NowUnfuzzed(), std::move(cause)));

    baseprofiler::profiler_add_marker(
        "UserTimingMarkerPayload", baseprofiler::ProfilingCategoryPair::OTHER,
        baseprofiler::UserTimingMarkerPayload("name", TimeStamp::NowUnfuzzed(),
                                              Nothing{}));

    baseprofiler::profiler_add_marker(
        "HangMarkerPayload", baseprofiler::ProfilingCategoryPair::OTHER,
        baseprofiler::HangMarkerPayload(TimeStamp::NowUnfuzzed(),
                                        TimeStamp::NowUnfuzzed()));

    baseprofiler::profiler_add_marker(
        "LongTaskMarkerPayload", baseprofiler::ProfilingCategoryPair::OTHER,
        baseprofiler::LongTaskMarkerPayload(TimeStamp::NowUnfuzzed(),
                                            TimeStamp::NowUnfuzzed()));

    {
      std::string s = "text payload";
      baseprofiler::profiler_add_marker(
          "TextMarkerPayload", baseprofiler::ProfilingCategoryPair::OTHER,
          baseprofiler::TextMarkerPayload(s, TimeStamp::NowUnfuzzed(),
                                          TimeStamp::NowUnfuzzed()));
    }

    baseprofiler::profiler_add_marker(
        "LogMarkerPayload", baseprofiler::ProfilingCategoryPair::OTHER,
        baseprofiler::LogMarkerPayload("module", "text",
                                       TimeStamp::NowUnfuzzed()));

    printf("Sleep 1s...\n");
    {
      AUTO_BASE_PROFILER_THREAD_SLEEP;
      SleepMilli(1000);
    }

    Maybe<baseprofiler::ProfilerBufferInfo> info =
        baseprofiler::profiler_get_buffer_info();
    MOZ_RELEASE_ASSERT(info.isSome());
    printf("Profiler buffer range: %llu .. %llu (%llu bytes)\n",
           static_cast<unsigned long long>(info->mRangeStart),
           static_cast<unsigned long long>(info->mRangeEnd),
           // sizeof(ProfileBufferEntry) == 9
           (static_cast<unsigned long long>(info->mRangeEnd) -
            static_cast<unsigned long long>(info->mRangeStart)) *
               9);
    printf("Stats:         min(ns) .. mean(ns) .. max(ns)  [count]\n");
    printf("- Intervals:   %7.1f .. %7.1f  .. %7.1f  [%u]\n",
           info->mIntervalsNs.min,
           info->mIntervalsNs.sum / info->mIntervalsNs.n,
           info->mIntervalsNs.max, info->mIntervalsNs.n);
    printf("- Overheads:   %7.1f .. %7.1f  .. %7.1f  [%u]\n",
           info->mOverheadsNs.min,
           info->mOverheadsNs.sum / info->mOverheadsNs.n,
           info->mOverheadsNs.max, info->mOverheadsNs.n);
    printf("  - Locking:   %7.1f .. %7.1f  .. %7.1f  [%u]\n",
           info->mLockingsNs.min, info->mLockingsNs.sum / info->mLockingsNs.n,
           info->mLockingsNs.max, info->mLockingsNs.n);
    printf("  - Clearning: %7.1f .. %7.1f  .. %7.1f  [%u]\n",
           info->mCleaningsNs.min,
           info->mCleaningsNs.sum / info->mCleaningsNs.n,
           info->mCleaningsNs.max, info->mCleaningsNs.n);
    printf("  - Counters:  %7.1f .. %7.1f  .. %7.1f  [%u]\n",
           info->mCountersNs.min, info->mCountersNs.sum / info->mCountersNs.n,
           info->mCountersNs.max, info->mCountersNs.n);
    printf("  - Threads:   %7.1f .. %7.1f  .. %7.1f  [%u]\n",
           info->mThreadsNs.min, info->mThreadsNs.sum / info->mThreadsNs.n,
           info->mThreadsNs.max, info->mThreadsNs.n);

    printf("baseprofiler_save_profile_to_file()...\n");
    baseprofiler::profiler_save_profile_to_file("TestProfiler_profile.json");

    printf("profiler_stop()...\n");
    baseprofiler::profiler_stop();

    MOZ_RELEASE_ASSERT(!baseprofiler::profiler_is_active());
    MOZ_RELEASE_ASSERT(!baseprofiler::profiler_thread_is_being_profiled());
    MOZ_RELEASE_ASSERT(!baseprofiler::profiler_thread_is_sleeping());

    printf("profiler_shutdown()...\n");
  }

  printf("TestProfiler done\n");
}

#else  // MOZ_GECKO_PROFILER

// Testing that macros are still #defined (but do nothing) when
// MOZ_GECKO_PROFILER is disabled.
void TestProfiler() {
  // These don't need to make sense, we just want to know that they're defined
  // and don't do anything.
  AUTO_BASE_PROFILER_INIT;

  // This wouldn't build if the macro did output its arguments.
  AUTO_BASE_PROFILER_TEXT_MARKER_CAUSE(catch, catch, catch, catch);

  AUTO_BASE_PROFILER_LABEL(catch, catch);

  AUTO_BASE_PROFILER_THREAD_SLEEP;
}

#endif  // MOZ_GECKO_PROFILER else

#if defined(XP_WIN)
int wmain()
#else
int main()
#endif  // defined(XP_WIN)
{
#ifdef MOZ_GECKO_PROFILER
  printf("BaseTestProfiler -- pid: %d, tid: %d\n",
         baseprofiler::profiler_current_process_id(),
         baseprofiler::profiler_current_thread_id());
  // ::SleepMilli(10000);
#endif  // MOZ_GECKO_PROFILER

  // Note that there are two `TestProfiler` functions above, depending on
  // whether MOZ_GECKO_PROFILER is #defined.
  TestProfiler();

  return 0;
}
'''

        cpp_content_2 = '''
#include <iostream>
using namespace std;

// Basic Function Declaration
int basicFunction(int a, int b) {
    return a + b;
}

// Inline Function
inline int inlineFunction(int a, int b) {
    return a * b;
}

// Const Member Function inside a Class
class MyClass {
public:
    int myMethod(int a) const {
        return a * a;
    }

    // Static Member Function
    static int staticMethod(int a) {
        return a * 2;
    }

    // Virtual Function
    virtual int virtualMethod(int a) {
        return a + 1;
    }

    // Pure Virtual Function
    virtual int pureVirtualMethod(int a) = 0;
};

// Friend Function
class AnotherClass {
    int x;
    friend int friendFunction(AnotherClass obj);
};

int friendFunction(AnotherClass obj) {
    return obj.x;
}

// Template Function
template <typename T>
T templateFunction(T a, T b) {
    return a > b ? a : b;
}

// Lambda Function
auto lambdaFunction = [](int a, int b) -> int {
    return a + b;
};

// Function Overloading
int overloadedFunction(int a, int b) {
    return a + b;
}

double overloadedFunction(double a, double b) {
    return a + b;
}

// Recursive Function
int recursiveFunction(int n) {
    if (n <= 1) return 1;
    return n * recursiveFunction(n - 1);
}

// Function with Default Parameters
int defaultParamFunction(int a, int b = 10) {
    return a + b;
}

// Function with Reference Parameters
void referenceFunction(int &a) {
    a = a * 2;
}

// Function with Pointer Parameters
void pointerFunction(int* ptr) {
    *ptr = *ptr + 1;
}

// Main Function
int main() {
    cout << "Test C++ Functions" << endl;
    return 0;
}
'''
        result = helper.extract_c_functions(cpp_content_1)
        self.print_result(result)
        
    ### Test function for 'extract_js_functions' ###
    def test_extract_js_functions(self):
        javascript_content_1 = '''
// Comment 1
/*
function commentFunction()
{
	Statement;
}
*/

let tuple = (1,2,'3');

function func_name0() {
    statement;
    "function name(){a}'` "
    `}}}{{}}`
}

let function1 = function(...) {
	statement;
}

const function2 = async function(...)
{
	statement;
}

let function3 = async (...) { statement }

const function4 = (...) => {
	statement
}

let function5 = function*(...)
{ statement }

const function6 = async function* (...)
{ statement }

let variable = "hello";

function function7(...)
{ statement }

async function* function8(...) {
	statement
}

function* function9(...) { statement }

random_string1(function (...) {
	statement
})

random_string2(function* (...)
	{
		statement
	}
)

random_string3(async function(...) { statement }, another_parameter)

random_string4(async function*(...) { statement })

random_string5((...) => { statement })

random_string6(async (...) => {
	statement
})

(function(...)
{
	statement1
})(...);

(function*(...)
{
	statement2
})(...);

(async function*(...)
{
	statement3
})(...);

(function*(...)
{
	statement4
})(...);

((...) =>
{
	statement5
})(...);

(async (...)
{
	statement6
})(...);

class className {
	constructor() {
		constructor statement;
	}
	
	let tuple = (1,2,'3');

	let function1 = function(...) {
		statement;
	}

	const function2 = async function(...)
	{
		statement;
	}

	let function3 = async (...) { statement }
	
	async function* function8(...) {
		statement
	}

	function* function9(...) { statement }

	random_string1(function (...) {
		statement
	})

	random_string2(function* (...)
		{
			statement
		}
	)

	random_string3(async function(...) { statement }, another_parameter)

	random_string4(async function*(...) { statement })
	
	(function(...)
	{
		statement1
	})(...);

	(function*(...)
	{
		statement2
	})(...);

	(async function*(...)
	{
		statement3
	})(...);

	(function*(...)
	{
		statement4
	})(...);

	((...) =>
	{
		statement5
	})(...);

	(async (...)
	{
		statement6
	})(...);
}
'''

        javascript_content_2 = '''
// Source file: https://hg.mozilla.org/releases/comm-esr91/raw-file/002d2d648a66fd8d9b8192589fba3eafcac697b8/mailnews/compose/test/unit/test_messageHeaders.js
/*
 * Test suite for ensuring that the headers of messages are set properly.
 */

var { Services } = ChromeUtils.import("resource://gre/modules/Services.jsm");
var { MailServices } = ChromeUtils.import(
  "resource:///modules/MailServices.jsm"
);
const { MimeParser } = ChromeUtils.import("resource:///modules/mimeParser.jsm");

var CompFields = CC(
  "@mozilla.org/messengercompose/composefields;1",
  Ci.nsIMsgCompFields
);

function makeAttachment(opts = {}) {
  let attachment = Cc[
    "@mozilla.org/messengercompose/attachment;1"
  ].createInstance(Ci.nsIMsgAttachment);
  for (let key in opts) {
    attachment[key] = opts[key];
  }
  return attachment;
}

function sendMessage(fieldParams, identity, opts = {}, attachments = []) {
  // Initialize compose fields
  let fields = new CompFields();
  for (let key in fieldParams) {
    fields[key] = fieldParams[key];
  }
  for (let attachment of attachments) {
    fields.addAttachment(attachment);
  }

  // Initialize compose params
  let params = Cc[
    "@mozilla.org/messengercompose/composeparams;1"
  ].createInstance(Ci.nsIMsgComposeParams);
  params.composeFields = fields;
  for (let key in opts) {
    params[key] = opts[key];
  }

  // Send the message
  let msgCompose = MailServices.compose.initCompose(params);
  let progress = Cc["@mozilla.org/messenger/progress;1"].createInstance(
    Ci.nsIMsgProgress
  );
  let promise = new Promise((resolve, reject) => {
    progressListener.resolve = resolve;
    progressListener.reject = reject;
  });
  progress.registerListener(progressListener);
  msgCompose.sendMsg(
    Ci.nsIMsgSend.nsMsgDeliverNow,
    identity,
    "",
    null,
    progress
  );
  return promise;
}

function checkDraftHeaders(expectedHeaders, partNum = "") {
  let msgData = mailTestUtils.loadMessageToString(
    gDraftFolder,
    mailTestUtils.firstMsgHdr(gDraftFolder)
  );
  checkMessageHeaders(msgData, expectedHeaders, partNum);
}

function checkMessageHeaders(msgData, expectedHeaders, partNum = "") {
  let seen = false;
  let handler = {
    startPart(part, headers) {
      if (part != partNum) {
        return;
      }
      seen = true;
      for (let header in expectedHeaders) {
        let expected = expectedHeaders[header];
        if (expected === undefined) {
          Assert.ok(
            !headers.has(header),
            `Should not have header named "${header}"`
          );
        } else {
          let value = headers.getRawHeader(header);
          Assert.equal(
            value && value.length,
            1,
            `Should have exactly one header named "${header}"`
          );
          value[0] = value[0].replace(/boundary=[^;]*(;|$)/, "boundary=.");
          Assert.equal(value[0], expected);
        }
      }
    },
  };
  MimeParser.parseSync(msgData, handler, {
    onerror(e) {
      throw e;
    },
  });
  Assert.ok(seen);
}

async function testEnvelope() {
  let fields = new CompFields();
  let identity = getSmtpIdentity(
    "from@tinderbox.invalid",
    getBasicSmtpServer()
  );
  identity.fullName = "Me";
  identity.organization = "World Destruction Committee";
  fields.from = "Nobody <nobody@tinderbox.invalid>";
  fields.to = "Nobody <nobody@tinderbox.invalid>";
  fields.cc = "Alex <alex@tinderbox.invalid>";
  fields.bcc = "Boris <boris@tinderbox.invalid>";
  fields.replyTo = "Charles <charles@tinderbox.invalid>";
  fields.organization = "World Salvation Committee";
  fields.subject = "This is an obscure reference";
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    // As of bug 87987, the identity does not override the from header.
    From: "Nobody <nobody@tinderbox.invalid>",
    // The identity should override the organization field here.
    Organization: "World Destruction Committee",
    To: "Nobody <nobody@tinderbox.invalid>",
    Cc: "Alex <alex@tinderbox.invalid>",
    Bcc: "Boris <boris@tinderbox.invalid>",
    "Reply-To": "Charles <charles@tinderbox.invalid>",
    Subject: "This is an obscure reference",
  });
}

async function testI18NEnvelope() {
  let fields = new CompFields();
  let identity = getSmtpIdentity(
    "from@tinderbox.invalid",
    getBasicSmtpServer()
  );
  identity.fullName = "ã‚±ãƒ„ã‚¡ãƒ«ã‚³ã‚¢ãƒˆãƒ«";
  identity.organization = "ComitÃ© de la destruction du monde";
  fields.to = "Ã‰mile <nobody@tinderbox.invalid>";
  fields.cc = "AndrÃ© Chopin <alex@tinderbox.invalid>";
  fields.bcc = "Ã‰tienne <boris@tinderbox.invalid>";
  fields.replyTo = "FrÃ©dÃ©ric <charles@tinderbox.invalid>";
  fields.subject = "Ceci n'est pas un rÃ©fÃ©rence obscure";
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    From:
      "=?UTF-8?B?44Kx44OE44Kh44Or44Kz44Ki44OI44Or?= <from@tinderbox.invalid>",
    Organization: "=?UTF-8?Q?Comit=c3=a9_de_la_destruction_du_monde?=",
    To: "=?UTF-8?B?w4ltaWxl?= <nobody@tinderbox.invalid>",
    Cc: "=?UTF-8?Q?Andr=c3=a9_Chopin?= <alex@tinderbox.invalid>",
    Bcc: "=?UTF-8?Q?=c3=89tienne?= <boris@tinderbox.invalid>",
    "Reply-To": "=?UTF-8?B?RnLDqWTDqXJpYw==?= <charles@tinderbox.invalid>",
    Subject: "=?UTF-8?Q?Ceci_n=27est_pas_un_r=c3=a9f=c3=a9rence_obscure?=",
  });
}

async function testIDNEnvelope() {
  let fields = new CompFields();
  let domain = "ã‚±ãƒ„ã‚¡ãƒ«ã‚³ã‚¢ãƒˆãƒ«.invalid";
  // We match against rawHeaderText, so we need to encode the string as a binary
  // string instead of a unicode string.
  let utf8Domain = String.fromCharCode.apply(
    undefined,
    new TextEncoder("UTF-8").encode(domain)
  );
  // Bug 1034658: nsIMsgIdentity doesn't like IDN in its email addresses.
  let identity = getSmtpIdentity(
    "from@tinderbox.invalid",
    getBasicSmtpServer()
  );
  fields.to = "Nobody <nobody@" + domain + ">";
  fields.cc = "Alex <alex@" + domain + ">";
  fields.bcc = "Boris <boris@" + domain + ">";
  fields.replyTo = "Charles <charles@" + domain + ">";
  fields.subject = "This is an obscure reference";
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    // The identity sets the from field here.
    From: "from@tinderbox.invalid",
    To: "Nobody <nobody@" + utf8Domain + ">",
    Cc: "Alex <alex@" + utf8Domain + ">",
    Bcc: "Boris <boris@" + utf8Domain + ">",
    "Reply-To": "Charles <charles@" + utf8Domain + ">",
    Subject: "This is an obscure reference",
  });
}

async function testDraftInfo() {
  let fields = new CompFields();
  let identity = getSmtpIdentity(
    "from@tinderbox.invalid",
    getBasicSmtpServer()
  );
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    FCC: identity.fccFolder,
    "X-Identity-Key": identity.key,
    "X-Mozilla-Draft-Info":
      "internal/draft; " +
      "vcard=0; receipt=0; DSN=0; uuencode=0; attachmentreminder=0; deliveryformat=4",
  });

  fields.attachVCard = true;
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "X-Mozilla-Draft-Info":
      "internal/draft; " +
      "vcard=1; receipt=0; DSN=0; uuencode=0; attachmentreminder=0; deliveryformat=4",
  });

  fields.returnReceipt = true;
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "X-Mozilla-Draft-Info":
      "internal/draft; " +
      "vcard=1; receipt=1; DSN=0; uuencode=0; attachmentreminder=0; deliveryformat=4",
  });

  fields.DSN = true;
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "X-Mozilla-Draft-Info":
      "internal/draft; " +
      "vcard=1; receipt=1; DSN=1; uuencode=0; attachmentreminder=0; deliveryformat=4",
  });

  fields.attachmentReminder = true;
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "X-Mozilla-Draft-Info":
      "internal/draft; " +
      "vcard=1; receipt=1; DSN=1; uuencode=0; attachmentreminder=1; deliveryformat=4",
  });

  fields.deliveryFormat = Ci.nsIMsgCompSendFormat.Both;
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "X-Mozilla-Draft-Info":
      "internal/draft; " +
      "vcard=1; receipt=1; DSN=1; uuencode=0; attachmentreminder=1; deliveryformat=3",
  });
}

async function testOtherHeaders() {
  let fields = new CompFields();
  let identity = getSmtpIdentity(
    "from@tinderbox.invalid",
    getBasicSmtpServer()
  );
  fields.priority = "high";
  fields.references = "<fake@tinderbox.invalid> <more@test.invalid>";
  fields.setHeader("X-Fake-Header", "124");
  let before = Date.now();
  let msgHdr = await richCreateMessage(fields, [], identity);
  let after = Date.now();
  let msgData = mailTestUtils.loadMessageToString(msgHdr.folder, msgHdr);
  checkMessageHeaders(msgData, {
    "Mime-Version": "1.0",
    "User-Agent": Cc["@mozilla.org/network/protocol;1?name=http"].getService(
      Ci.nsIHttpProtocolHandler
    ).userAgent,
    "X-Priority": "2 (High)",
    References: "<fake@tinderbox.invalid> <more@test.invalid>",
    "In-Reply-To": "<more@test.invalid>",
    "X-Fake-Header": "124",
  });

  // Check headers with dynamic content
  let headers = MimeParser.extractHeaders(msgData);
  Assert.ok(headers.has("Message-Id"));
  Assert.ok(
    headers.getRawHeader("Message-Id")[0].endsWith("@tinderbox.invalid>")
  );
  // This is a very special crafted check. We don't know when the message was
  // actually created, but we have bounds on it, from above. From
  // experimentation, there are a few ways you can create dates that Date.parse
  // can't handle (specifically related to how 2-digit years). However, the
  // optimal RFC 5322 form is supported by Date.parse. If Date.parse fails, we
  // have a form that we shouldn't be using anyways.
  let date = new Date(headers.getRawHeader("Date")[0]);
  // If we have clock skew within the test, then our results are going to be
  // meaningless. Hopefully, this is only rarely the case.
  if (before > after) {
    info("Clock skew detected, skipping date check");
  } else {
    // In case this all took place within one second, remove sub-millisecond
    // timing (Date headers only carry second-level precision).
    before = before - (before % 1000);
    after = after - (after % 1000);
    info(before + " <= " + date + " <= " + after + "?");
    Assert.ok(before <= date && date <= after);
  }

  // We truncate too-long References. Check this.
  let references = [];
  for (let i = 0; i < 100; i++) {
    references.push("<" + i + "@test.invalid>");
  }
  let expected = references.slice(47);
  expected.unshift(references[0]);
  fields.references = references.join(" ");
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    References: expected.join(" "),
    "In-Reply-To": references[references.length - 1],
  });
}

async function testNewsgroups() {
  let fields = new CompFields();
  let nntpServer = localAccountUtils.create_incoming_server(
    "nntp",
    534,
    "",
    ""
  );
  nntpServer
    .QueryInterface(Ci.nsINntpIncomingServer)
    .subscribeToNewsgroup("mozilla.test");
  let identity = getSmtpIdentity(
    "from@tinderbox.invalid",
    getBasicSmtpServer()
  );
  fields.newsgroups = "mozilla.test, mozilla.test.multimedia";
  fields.followupTo = "mozilla.test";
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    // The identity should override the compose fields here.
    Newsgroups: "mozilla.test,mozilla.test.multimedia",
    "Followup-To": "mozilla.test",
    "X-Mozilla-News-Host": "localhost",
  });
}

async function testSendHeaders() {
  let fields = new CompFields();
  let identity = getSmtpIdentity(
    "from@tinderbox.invalid",
    getBasicSmtpServer()
  );
  identity.setCharAttribute("headers", "bah,humbug");
  identity.setCharAttribute(
    "header.bah",
    "X-Custom-1: A header value: with a colon"
  );
  identity.setUnicharAttribute("header.humbug", "X-Custom-2: EnchantÃ©");
  identity.setCharAttribute("subscribed_mailing_lists", "list@test.invalid");
  identity.setCharAttribute(
    "replyto_mangling_mailing_lists",
    "replyto@test.invalid"
  );
  fields.to = "list@test.invalid";
  fields.cc = "not-list@test.invalid";
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "X-Custom-1": "A header value: with a colon",
    "X-Custom-2": "=?UTF-8?B?RW5jaGFudMOp?=",
    "Mail-Followup-To": "list@test.invalid, not-list@test.invalid",
    "Mail-Reply-To": undefined,
  });

  // Don't set the M-F-T header if there's no list.
  fields.to = "replyto@test.invalid";
  fields.cc = "";
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "X-Custom-1": "A header value: with a colon",
    "X-Custom-2": "=?UTF-8?B?RW5jaGFudMOp?=",
    "Mail-Reply-To": "from@tinderbox.invalid",
    "Mail-Followup-To": undefined,
  });
}

async function testContentHeaders() {
  // Disable RFC 2047 fallback
  Services.prefs.setIntPref("mail.strictly_mime.parm_folding", 2);
  let fields = new CompFields();
  fields.body = "A body";
  let identity = getSmtpIdentity(
    "from@tinderbox.invalid",
    getBasicSmtpServer()
  );
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "Content-Type": "text/html; charset=UTF-8",
    "Content-Transfer-Encoding": "7bit",
  });

  // non-ASCII body should be 8-bit...
  fields.body = "ArchÃ¦ologist";
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "Content-Type": "text/html; charset=UTF-8",
    "Content-Transfer-Encoding": "8bit",
  });

  // Attachments
  fields.body = "";
  let plainAttachment = makeAttachment({
    url: "data:text/plain,oÃ¯l",
    name: "attachment.txt",
  });
  let plainAttachmentHeaders = {
    "Content-Type": "text/plain; charset=UTF-8",
    "Content-Transfer-Encoding": "base64",
    "Content-Disposition": 'attachment; filename="attachment.txt"',
  };
  await richCreateMessage(fields, [plainAttachment], identity);
  checkDraftHeaders(
    {
      "Content-Type": "text/html; charset=UTF-8",
      "Content-Transfer-Encoding": "7bit",
    },
    "1"
  );
  checkDraftHeaders(plainAttachmentHeaders, "2");

  plainAttachment.name = "oÃ¯l.txt";
  plainAttachmentHeaders["Content-Disposition"] =
    "attachment; filename*=UTF-8''%6F%C3%AF%6C%2E%74%78%74";
  await richCreateMessage(fields, [plainAttachment], identity);
  checkDraftHeaders(plainAttachmentHeaders, "2");

  plainAttachment.name = "\ud83d\udca9.txt";
  plainAttachmentHeaders["Content-Disposition"] =
    "attachment; filename*=UTF-8''%F0%9F%92%A9%2E%74%78%74";
  await richCreateMessage(fields, [plainAttachment], identity);
  checkDraftHeaders(plainAttachmentHeaders, "2");

  let httpAttachment = makeAttachment({
    url: "data:text/html,<html></html>",
    name: "attachment.html",
  });
  let httpAttachmentHeaders = {
    "Content-Type": "text/html; charset=UTF-8",
    "Content-Disposition": 'attachment; filename="attachment.html"',
    "Content-Location": "data:text/html,<html></html>",
  };
  await richCreateMessage(fields, [httpAttachment], identity);
  checkDraftHeaders(
    {
      "Content-Location": undefined,
    },
    "1"
  );
  checkDraftHeaders(httpAttachmentHeaders, "2");

  let cloudAttachment = makeAttachment({
    url: Services.io.newFileURI(do_get_file("data/test-UTF-8.txt")).spec,
    sendViaCloud: true,
    cloudFileAccountKey: "akey",
    name: "attachment.html",
    contentLocation: "http://localhost.invalid/",
  });
  let cloudAttachmentHeaders = {
    "Content-Type": "application/octet-stream",
    "X-Mozilla-Cloud-Part":
      "cloudFile; url=http://localhost.invalid/; " +
      "provider=akey; " +
      "file=" +
      cloudAttachment.url +
      '; name="attachment.html"',
  };
  await richCreateMessage(fields, [cloudAttachment], identity);
  checkDraftHeaders(cloudAttachmentHeaders, "2");

  // Cloud attachment with non-ascii file name.
  cloudAttachment = makeAttachment({
    url: Services.io.newFileURI(do_get_file("data/test-UTF-8.txt")).spec,
    sendViaCloud: true,
    cloudFileAccountKey: "akey",
    name: "ãƒ•ã‚¡ã‚¤ãƒ«.txt",
    contentLocation: "http://localhost.invalid/",
  });
  cloudAttachmentHeaders = {
    "Content-Type": "application/octet-stream",
    "X-Mozilla-Cloud-Part":
      "cloudFile; url=http://localhost.invalid/; " +
      "provider=akey; " +
      "file=" +
      cloudAttachment.url +
      "; name*=UTF-8''%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB%2E%74%78%74",
  };
  await richCreateMessage(fields, [cloudAttachment], identity);
  checkDraftHeaders(cloudAttachmentHeaders, "2");

  // Some multipart/alternative tests.
  fields.body = "Some text";
  fields.forcePlainText = false;
  fields.useMultipartAlternative = true;
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "Content-Type": "multipart/alternative; boundary=.",
  });
  checkDraftHeaders(
    {
      "Content-Type": "text/plain; charset=UTF-8; format=flowed",
      "Content-Transfer-Encoding": "7bit",
    },
    "1"
  );
  checkDraftHeaders(
    {
      "Content-Type": "text/html; charset=UTF-8",
      "Content-Transfer-Encoding": "7bit",
    },
    "2"
  );

  // multipart/mixed
  // + multipart/alternative
  //   + text/plain
  //   + text/html
  // + text/plain attachment
  await richCreateMessage(fields, [plainAttachment], identity);
  checkDraftHeaders({
    "Content-Type": "multipart/mixed; boundary=.",
  });
  checkDraftHeaders(
    {
      "Content-Type": "multipart/alternative; boundary=.",
    },
    "1"
  );
  checkDraftHeaders(
    {
      "Content-Type": "text/plain; charset=UTF-8; format=flowed",
      "Content-Transfer-Encoding": "7bit",
    },
    "1.1"
  );
  checkDraftHeaders(
    {
      "Content-Type": "text/html; charset=UTF-8",
      "Content-Transfer-Encoding": "7bit",
    },
    "1.2"
  );
  checkDraftHeaders(plainAttachmentHeaders, "2");

  // Three attachments, and a multipart/alternative. Oh the humanity!
  await richCreateMessage(
    fields,
    [plainAttachment, httpAttachment, cloudAttachment],
    identity
  );
  checkDraftHeaders({
    "Content-Type": "multipart/mixed; boundary=.",
  });
  checkDraftHeaders(
    {
      "Content-Type": "multipart/alternative; boundary=.",
    },
    "1"
  );
  checkDraftHeaders(
    {
      "Content-Type": "text/plain; charset=UTF-8; format=flowed",
      "Content-Transfer-Encoding": "7bit",
    },
    "1.1"
  );
  checkDraftHeaders(
    {
      "Content-Type": "text/html; charset=UTF-8",
      "Content-Transfer-Encoding": "7bit",
    },
    "1.2"
  );
  checkDraftHeaders(cloudAttachmentHeaders, "2");
  checkDraftHeaders(plainAttachmentHeaders, "3");
  checkDraftHeaders(httpAttachmentHeaders, "4");

  // Test a request for plain text with text/html.
  fields.forcePlainText = true;
  fields.useMultipartAlternative = false;
  await richCreateMessage(fields, [], identity);
  checkDraftHeaders({
    "Content-Type": "text/plain; charset=UTF-8; format=flowed",
    "Content-Transfer-Encoding": "7bit",
  });
}

async function testSentMessage() {
  let server = setupServerDaemon();
  let daemon = server._daemon;
  server.start();
  try {
    let localserver = getBasicSmtpServer(server.port);
    let identity = getSmtpIdentity("test@tinderbox.invalid", localserver);
    await sendMessage(
      {
        to: "Nobody <nobody@tinderbox.invalid>",
        cc: "Alex <alex@tinderbox.invalid>",
        bcc: "Boris <boris@tinderbox.invalid>",
        replyTo: "Charles <charles@tinderbox.invalid>",
      },
      identity,
      {},
      []
    );
    server.performTest();
    checkMessageHeaders(daemon.post, {
      From: "test@tinderbox.invalid",
      To: "Nobody <nobody@tinderbox.invalid>",
      Cc: "Alex <alex@tinderbox.invalid>",
      Bcc: undefined,
      "Reply-To": "Charles <charles@tinderbox.invalid>",
      "X-Mozilla-Status": undefined,
      "X-Mozilla-Keys": undefined,
      "X-Mozilla-Draft-Info": undefined,
      Fcc: undefined,
    });
    server.resetTest();
    await sendMessage({ bcc: "Somebody <test@tinderbox.invalid" }, identity);
    server.performTest();
    checkMessageHeaders(daemon.post, {
      To: "undisclosed-recipients: ;",
    });
    server.resetTest();
    await sendMessage(
      {
        to: "Somebody <test@tinderbox.invalid>",
        returnReceipt: true,
        receiptHeaderType: Ci.nsIMsgMdnGenerator.eDntRrtType,
      },
      identity
    );
    server.performTest();
    checkMessageHeaders(daemon.post, {
      "Disposition-Notification-To": "test@tinderbox.invalid",
      "Return-Receipt-To": "test@tinderbox.invalid",
    });
    server.resetTest();
    let cloudAttachment = makeAttachment({
      url: Services.io.newFileURI(do_get_file("data/test-UTF-8.txt")).spec,
      sendViaCloud: true,
      cloudFileAccountKey: "akey",
      name: "attachment.html",
      contentLocation: "http://localhost.invalid/",
    });
    await sendMessage({ to: "test@tinderbox.invalid" }, identity, {}, [
      cloudAttachment,
    ]);
    server.performTest();
    checkMessageHeaders(
      daemon.post,
      {
        "Content-Type": "application/octet-stream",
        "X-Mozilla-Cloud-Part":
          'cloudFile; url=http://localhost.invalid/; name="attachment.html"',
      },
      "2"
    );
  } finally {
    server.stop();
  }
}

var tests = [
  testEnvelope,
  testI18NEnvelope,
  testIDNEnvelope,
  testDraftInfo,
  testOtherHeaders,
  testNewsgroups,
  testSendHeaders,
  testContentHeaders,
  testSentMessage,
];

function run_test() {
  // Ensure we have at least one mail account
  localAccountUtils.loadLocalMailAccount();
  tests.forEach(x => add_task(x));
  run_next_test();
}
'''

        javascript_content_3 = '''
;
class className {
	constructor() {
		constructor statement;
	}
	
	let tuple = (1,2,'3');

	let function1 = function(...) {
		statement;
	}
}
'''


        # Test remove_js_comments function:
        # content_without_comments = helper.remove_js_comments(javascript_content_1)
        # print(content_without_comments)

        result = helper.extract_js_functions(javascript_content_1)
        self.print_result(result)



## End of class [ExtractFunctionTest]



##############################################################################
##############################################################################

# if __name__ == '__main__':
    # Run all test functions:
    # unittest.main(argv=['first-arg-is-ignored'], exit=False)

    # Run a specific test function:
    unittest.main(argv=['first-arg-is-ignored', 'ExtractFunctionTest.test_extract_js_functions'], exit=False)
