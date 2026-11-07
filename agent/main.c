#include "pp.h"
#include <sys/neutrino.h>
#include <sys/syspage.h>
#include <sys/utsname.h>
#include <pthread.h>
#include <sched.h>
#include <time.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <inttypes.h>

static int number(const char *s,unsigned *out,unsigned min,unsigned max) {
    char *end;errno=0;
    if(!s[0] || s[0]=='-') return -1;
    unsigned long v=strtoul(s,&end,10);
    if(errno || *end || v<min || v>max) return -1;
    *out=(unsigned)v;return 0;
}

static uint64_t process_cpu(void) {
    struct timespec ts;
    if(clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&ts)!=0) return 0;
    return (uint64_t)ts.tv_sec*1000000000ULL+(uint64_t)ts.tv_nsec;
}

int main(int argc,char **argv) {
    pp_config c={0};
    if(argc!=12 || (strcmp(argv[1],"timer") && strcmp(argv[1],"ipc") && strcmp(argv[1],"service"))) {
        fprintf(stderr,"usage: pp-agent timer|ipc|service samples period_us deadline_us work_us load_threads fault_every fault_delay_us timeout_us priority protocol_version\n");return 2;
    }
    c.mode=argv[1];
    unsigned *fields[]={&c.samples,&c.period_us,&c.deadline_us,&c.work_us,&c.load_threads,&c.fault_every,&c.fault_delay_us,&c.timeout_us,&c.priority};
    unsigned limits[]={10000,1000000,1000000,100000,8,10000,100000,1000000,50};
    for(unsigned i=0;i<9;++i) if(number(argv[i+2],fields[i],i==0||i==1||i==2||i==7||i==8 ? 1:0,limits[i])) {fprintf(stderr,"invalid argument %u\n",i+2);return 2;}
    if(!strcmp(c.mode,"service") && (c.work_us || c.load_threads || c.fault_every || c.fault_delay_us)) {fprintf(stderr,"service workload belongs to the independent application\n");return 2;}
    uint64_t per_job=!strcmp(c.mode,"timer") && c.period_us>c.work_us ? c.period_us:c.work_us;
    uint64_t planned=c.samples*per_job+(uint64_t)(c.fault_every?c.samples/c.fault_every:0)*c.fault_delay_us;
    if(strcmp(argv[11],"1") || (uint64_t)c.samples*c.period_us>30000000ULL || planned>30000000ULL || (c.fault_every && c.fault_every<2)) {fprintf(stderr,"scenario exceeds bounds or protocol unsupported\n");return 2;}
    signal(SIGALRM,pp_watchdog);signal(SIGTERM,pp_watchdog);signal(SIGINT,pp_watchdog);alarm(60);
    struct sched_param sp={0};sp.sched_priority=(int)c.priority;
    int scheduling_error=pthread_setschedparam(pthread_self(),SCHED_RR,&sp);
    if(scheduling_error) {fprintf(stderr,"SCHED_RR failed: %s\n",strerror(scheduling_error));return 2;}
    int policy=0;pthread_getschedparam(pthread_self(),&policy,&sp);
    struct _clockperiod tick={0};
    if(ClockPeriod(CLOCK_REALTIME,NULL,&tick,0)<0) {perror("ClockPeriod");return 2;}
    struct timespec resolution={0};clock_getres(CLOCK_MONOTONIC,&resolution);
    struct utsname u;if(uname(&u)!=0 || strcmp(u.sysname,"QNX")) {fprintf(stderr,"QNX target required\n");return 2;}
    uint64_t overhead=UINT64_MAX;
    for(unsigned i=0;i<1000;++i) {uint64_t a=pp_now(),b=pp_now();if(b-a<overhead) overhead=b-a;}
    pp_sample *samples=calloc(c.samples,sizeof(*samples));
    if(!samples) {perror("calloc");return 2;}
    if(!strcmp(c.mode,"ipc") && pp_ipc_start(&c)<0) {perror("IPC startup");free(samples);return 2;}
    if(!strcmp(c.mode,"service") && pp_service_start()<0) {perror("service startup");free(samples);return 2;}
    if(pp_load_start(c.load_threads)) {fprintf(stderr,"load thread startup failed\n");pp_ipc_stop();free(samples);return 2;}
    uint64_t idle_start=0,idle_end=0,obs_start=0,obs_end=0;
    int system_available=pp_system_init((unsigned)_syspage_ptr->num_cpu)==0 && pp_system_snapshot(&idle_start,&obs_start)==0;
    uint64_t cpu_start=process_cpu(),wall_start=pp_now();
    time_t epoch=time(NULL);
    int rc=!strcmp(c.mode,"timer") ? pp_timer(&c,samples):!strcmp(c.mode,"ipc")?pp_ipc(&c,samples):pp_service(&c,samples);
    uint64_t elapsed=pp_now()-wall_start,cpu=process_cpu()-cpu_start;
    system_available=system_available && pp_system_snapshot(&idle_end,&obs_end)==0 && idle_end>=idle_start && obs_end>obs_start;
    pp_load_stop();pp_ipc_stop();pp_service_stop();alarm(0);
    if(rc) {perror("measurement failed");free(samples);return 2;}
    /* Emit only after measurement. No stdout IO in the measured loops. */
    printf("{\"type\":\"metadata\",\"schema_version\":1,\"source\":\"qnx-native\",\"agent_version\":\"0.2.0-rc1\",\"os\":\"QNX\",\"release\":\"%s\",\"arch\":\"x86_64\",\"machine\":\"%s\",\"clock\":\"CLOCK_MONOTONIC\",\"mode\":\"%s\",\"samples\":%u,\"period_us\":%u,\"deadline_us\":%u,\"work_us\":%u,\"load_threads\":%u,\"fault_every\":%u,\"fault_delay_us\":%u,\"timeout_us\":%u,\"priority\":%d,\"scheduler\":\"SCHED_RR\",\"cpu_count\":%u,\"tick_ns\":%lu,\"clock_resolution_ns\":%" PRIu64 ",\"clock_read_min_ns\":%" PRIu64 ",\"cycles_per_second\":%" PRIu64 ",\"started_epoch\":%ld,\"timeout_errno\":%d,\"service_build\":%u}\n",
        u.release,u.machine,c.mode,c.samples,c.period_us,c.deadline_us,c.work_us,c.load_threads,c.fault_every,c.fault_delay_us,c.timeout_us,sp.sched_priority,(unsigned)_syspage_ptr->num_cpu,(unsigned long)tick.nsec,(uint64_t)((uint64_t)resolution.tv_sec*1000000000ULL+(uint64_t)resolution.tv_nsec),overhead,(uint64_t)SYSPAGE_ENTRY(qtime)->cycles_per_sec,(long)epoch,ETIMEDOUT,pp_service_build());
    for(unsigned i=0;i<c.samples;++i) {
        pp_sample *s=&samples[i];
        printf("{\"type\":\"sample\",\"sequence\":%u,\"latency_ns\":%" PRIu64 ",\"wake_lateness_ns\":%" PRIu64 ",\"error\":%d,\"timeout\":%s,\"injected\":%s,\"recovery\":%s,\"deadline_miss\":%s,\"deadline_unobserved\":%s}\n",i,s->latency_ns,s->wake_lateness_ns,s->error,s->error==ETIMEDOUT?"true":"false",s->injected?"true":"false",s->recovery?"true":"false",!s->error && s->latency_ns>(uint64_t)c.deadline_us*1000?"true":"false",s->error?"true":"false");
    }
    printf("{\"type\":\"complete\",\"samples\":%u,\"elapsed_ns\":%" PRIu64 ",\"process_cpu_ns\":%" PRIu64 ",\"system_cpu_available\":%s,\"idle_cpu_ns\":%" PRIu64 ",\"cpu_observation_ns\":%" PRIu64 "}\n",c.samples,elapsed,cpu,system_available?"true":"false",system_available?idle_end-idle_start:0,system_available?obs_end-obs_start:0);
    free(samples);return ferror(stdout)?2:0;
}



