CXX ?= g++
CXXFLAGS ?= -std=c++11 -O2 -Wall
.PHONY: all clean broken
all: ref ref_fp8
ref: ref.cpp
	$(CXX) $(CXXFLAGS) -o ref ref.cpp
ref_fp8: ref_fp8.cpp
	$(CXX) $(CXXFLAGS) -o ref_fp8 ref_fp8.cpp
broken: ref_broken.cpp
	$(CXX) $(CXXFLAGS) -o ref_broken ref_broken.cpp
clean:
	rm -f ref ref_broken ref_fp8
