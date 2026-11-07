/* Independent example application: a deterministic telemetry acquisition service.
 * The data value is a fixture. Request timing is measured on the actual QNX kernel.
 */
#include "protocol.h"
#include <sys/dispatch.h>
#include <sys/neutrino.h>
#include <sys/iomsg.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <stdlib.h>
#ifndef SERVICE_DELAY_US
#define SERVICE_DELAY_US 0
#endif
#ifndef SERVICE_BUILD_ID
#define SERVICE_BUILD_ID 1
#endif

int main(int argc,char **argv) {
    if(argc!=2) return 2;
    char *end;errno=0;uint64_t instance=strtoull(argv[1],&end,16);
    if(errno || *end || !instance) return 2;
    /* No inherited SIGHUP from the noninteractive host SSH launch. */
    alarm(45);
    name_attach_t *attach=name_attach(NULL,PP_SERVICE_NAME,0);
    if(!attach) {perror("name_attach");return 2;}
    printf("telemetry service ready: protocol=%d build=%d delay_us=%d\n",PP_SERVICE_PROTOCOL,SERVICE_BUILD_ID,SERVICE_DELAY_US);
    fflush(stdout);
    for(;;) {
        union {struct _pulse pulse;pp_read_request request;} message;
        memset(&message,0,sizeof(message));
        struct _msg_info info;
        int rid=(int)MsgReceive(attach->chid,&message,sizeof(message),&info);
        if(rid<0) {if(errno==EINTR)continue;perror("MsgReceive");break;}
        if(rid==0) {
            if(message.pulse.code==_PULSE_CODE_DISCONNECT) ConnectDetach(message.pulse.scoid);
            else if(message.pulse.code==_PULSE_CODE_UNBLOCK) MsgError(message.pulse.value.sival_int,ETIMEDOUT);
            continue;
        }
        if(message.request.type==_IO_CONNECT) {MsgReply(rid,0,NULL,0);continue;}
        if(info.msglen!=(int)sizeof(pp_read_request) || message.request.type!=PP_READ_SAMPLE || message.request.version!=PP_SERVICE_PROTOCOL) {
            MsgError(rid,EPROTO);continue;
        }
        /* The regressed build adds blocking work on the service's request path. */
        if(SERVICE_DELAY_US) {
            struct timespec delay={0,SERVICE_DELAY_US*1000L};
            while(nanosleep(&delay,&delay)<0 && errno==EINTR) {}
        }
        pp_read_reply reply={message.request.sequence,SERVICE_BUILD_ID,22500+(int32_t)(message.request.sequence%10),instance};
        if(MsgReply(rid,0,&reply,sizeof(reply))<0 && errno!=ESRCH) {perror("MsgReply");break;}
    }
    name_detach(attach,0);return 2;
}
