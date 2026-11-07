/* Guest-wide utilization from verified procnto idle thread CPU-time clocks. */
#include "pp.h"
#include <sys/neutrino.h>
#include <stdio.h>
#include <string.h>

static int clocks[256];
static unsigned count;

int pp_system_init(unsigned cpus) {
    if(!cpus || cpus>256) return -1;
    for(unsigned cpu=0;cpu<cpus;++cpu) {
        struct {int new_name_len;int name_buf_len;char name_buf[101];} name;
        memset(&name,0,sizeof(name));name.new_name_len=-1;name.name_buf_len=sizeof(name.name_buf);
        if(ThreadCtlExt(1,(int)cpu+1,_NTO_TCTL_NAME,&name)<0) return -1;
        char expected[32];snprintf(expected,sizeof(expected),"idle_cpu_%u",cpu);
        if(strcmp(name.name_buf,expected)) return -1;
        clocks[cpu]=ClockId(1,(int)cpu+1);
        if(clocks[cpu]<0) return -1;
    }
    count=cpus;return 0;
}

int pp_system_snapshot(uint64_t *idle_ns,uint64_t *midpoint_ns) {
    if(!count) return -1;
    uint64_t start=pp_now(),sum=0;
    for(unsigned cpu=0;cpu<count;++cpu) {
        uint64_t value;
        if(ClockTime(clocks[cpu],NULL,&value)<0) return -1;
        sum+=value;
    }
    *idle_ns=sum;*midpoint_ns=start+(pp_now()-start)/2;return 0;
}
