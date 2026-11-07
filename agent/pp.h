#ifndef PP_H
#define PP_H
#include <stdint.h>
#include <stddef.h>

typedef struct {
    const char *mode;
    unsigned samples, period_us, deadline_us, work_us, load_threads;
    unsigned fault_every, fault_delay_us, timeout_us, priority;
} pp_config;

typedef struct {
    uint64_t latency_ns, wake_lateness_ns;
    int error, injected, recovery;
} pp_sample;

uint64_t pp_now(void);
void pp_sleep_us(unsigned us);
void pp_busy_us(unsigned us);
int pp_timer(const pp_config *c, pp_sample *out);
int pp_ipc_start(const pp_config *c);
int pp_ipc(const pp_config *c, pp_sample *out);
void pp_ipc_stop(void);
int pp_load_start(unsigned count);
void pp_load_stop(void);
void pp_watchdog(int signo);
int pp_system_init(unsigned cpus);
int pp_system_snapshot(uint64_t *idle_ns,uint64_t *midpoint_ns);
int pp_service_start(void);
int pp_service(const pp_config *c,pp_sample *samples);
void pp_service_stop(void);
unsigned pp_service_build(void);
#endif
