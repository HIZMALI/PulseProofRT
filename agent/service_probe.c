#include "pp.h"
#include "../examples/telemetry-service/protocol.h"
#include <sys/dispatch.h>
#include <sys/neutrino.h>
#include <errno.h>
#include <stdlib.h>

static int connection=-1;
static unsigned build_id;
static uint64_t instance;

int pp_service_start(void) {
    const char *configured=getenv("PP_SERVICE_INSTANCE");char *end;
    if(!configured) {errno=EINVAL;return -1;}
    errno=0;instance=strtoull(configured,&end,16);
    if(errno || *end || !instance) {errno=EINVAL;return -1;}
    for(unsigned i=0;i<300;++i) {
        connection=name_open(PP_SERVICE_NAME,0);
        if(connection>=0) return 0;
        if(errno!=ENOENT) return -1;
        pp_sleep_us(10000);
    }
    errno=ETIMEDOUT;return -1;
}

static int request(unsigned sequence,unsigned timeout_us) {
    pp_read_request send={PP_READ_SAMPLE,PP_SERVICE_PROTOCOL,sequence};
    pp_read_reply reply={0};
    uint64_t timeout=(uint64_t)timeout_us*1000;
    if(TimerTimeout(CLOCK_MONOTONIC,_NTO_TIMEOUT_SEND|_NTO_TIMEOUT_REPLY,NULL,&timeout,NULL)<0) return errno;
    if(MsgSend(connection,&send,sizeof(send),&reply,sizeof(reply))<0) return errno;
    if(reply.sequence!=sequence || reply.instance!=instance || reply.value_millicelsius!=22500+(int32_t)(sequence%10) || (build_id && reply.build_id!=build_id)) return EPROTO;
    build_id=reply.build_id;
    return build_id==1 || build_id==2 ? 0:EPROTO;
}

int pp_service(const pp_config *c,pp_sample *samples) {
    for(unsigned i=0;i<20;++i) {int error=request(0,c->timeout_us);if(error){errno=error;return -1;}}
    int previous_timeout=0;
    for(unsigned i=0;i<c->samples;++i) {
        samples[i].recovery=previous_timeout;
        uint64_t start=pp_now();
        samples[i].error=request(i+1,c->timeout_us);
        samples[i].latency_ns=pp_now()-start;
        previous_timeout=samples[i].error==ETIMEDOUT;
    }
    return 0;
}

void pp_service_stop(void) {if(connection>=0){name_close(connection);connection=-1;}}
unsigned pp_service_build(void) {return build_id;}
