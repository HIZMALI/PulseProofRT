#include "pp.h"
#include <errno.h>
#include <time.h>

uint64_t pp_now(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0;
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

void pp_sleep_us(unsigned us) {
    struct timespec t = {us / 1000000, (long)(us % 1000000) * 1000};
    while (nanosleep(&t, &t) != 0 && errno == EINTR) {}
}

void pp_busy_us(unsigned us) {
    uint64_t end = pp_now() + (uint64_t)us * 1000;
    volatile unsigned x = 1;
    while (pp_now() < end) { for (unsigned j=0; j<64; ++j) x=x*1664525U+1013904223U; }
    (void)x;
}

int pp_timer(const pp_config *c, pp_sample *out) {
    uint64_t release = pp_now() + (uint64_t)c->period_us * 1000;
    for (unsigned i=0; i<c->samples; ++i) {
        struct timespec at = {(time_t)(release/1000000000ULL), (long)(release%1000000000ULL)};
        int rc;
        do { rc=clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &at, NULL); } while(rc==EINTR);
        if(rc!=0) { errno=rc; return -1; }
        uint64_t wake=pp_now();
        out[i].wake_lateness_ns = wake>release ? wake-release : 0;
        pp_busy_us(c->work_us);
        out[i].injected = c->fault_every && (i+1)%c->fault_every==0;
        if(out[i].injected) pp_sleep_us(c->fault_delay_us);
        out[i].latency_ns=pp_now()-release;
        release += (uint64_t)c->period_us * 1000;
    }
    return 0;
}
