#include "pp.h"
#include <sys/neutrino.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <poll.h>
#include <stdlib.h>

static volatile sig_atomic_t child_pid;
static int connection=-1;
typedef struct { uint32_t sequence; } request;

void pp_watchdog(int signo) {
    (void)signo;
    if(child_pid>0) kill((pid_t)child_pid,SIGKILL);
    _exit(124);
}

static void server(const pp_config *c,int ready) {
    alarm(65);
    int channel=ChannelCreate(0);
    if(write(ready,&channel,sizeof(channel))!=(ssize_t)sizeof(channel) || channel<0) _exit(2);
    close(ready);
    for(;;) {
        request req;
        long rid=MsgReceive(channel,&req,sizeof(req),NULL);
        if(rid<0) {if(errno==EINTR) continue; _exit(3);}
        if(rid==0) continue;
        if(c->fault_every && req.sequence && req.sequence%c->fault_every==0) pp_sleep_us(c->fault_delay_us);
        pp_busy_us(c->work_us);
        if(MsgReply((int)rid,0,&req,sizeof(req))<0 && errno!=ESRCH) _exit(4);
    }
}

int pp_ipc_start(const pp_config *c) {
    int fds[2];
    if(pipe(fds)!=0) return -1;
    pid_t pid=fork();
    if(pid<0) {close(fds[0]);close(fds[1]);return -1;}
    if(pid==0) {close(fds[0]);server(c,fds[1]);_exit(5);}
    child_pid=pid;
    close(fds[1]);
    struct pollfd p={fds[0],POLLIN,0};
    int channel=-1;
    int n=poll(&p,1,3000);
    ssize_t got=n>0 ? read(fds[0],&channel,sizeof(channel)) : -1;
    close(fds[0]);
    if(got!=(ssize_t)sizeof(channel) || channel<0) {pp_ipc_stop();errno=ETIMEDOUT;return -1;}
    connection=ConnectAttach(0,pid,channel,_NTO_SIDE_CHANNEL,0);
    if(connection<0) {pp_ipc_stop();return -1;}
    return 0;
}

static int exchange(uint32_t seq,unsigned timeout_us) {
    request send={seq}, reply={0};
    uint64_t timeout=(uint64_t)timeout_us*1000;
    if(TimerTimeout(CLOCK_MONOTONIC,_NTO_TIMEOUT_SEND|_NTO_TIMEOUT_REPLY,NULL,&timeout,NULL)<0) return errno;
    if(MsgSend(connection,&send,sizeof(send),&reply,sizeof(reply))<0) return errno;
    return reply.sequence==seq ? 0 : EPROTO;
}

int pp_ipc(const pp_config *c,pp_sample *out) {
    for(unsigned i=0;i<20;++i) {int e=exchange(0,250000);if(e){errno=e;return -1;}}
    int recovering=0;
    for(unsigned i=0;i<c->samples;++i) {
        out[i].injected=c->fault_every && (i+1)%c->fault_every==0;
        out[i].recovery=recovering;
        uint64_t start=pp_now();
        out[i].error=exchange(i+1,recovering ? 250000 : c->timeout_us);
        out[i].latency_ns=pp_now()-start;
        recovering=out[i].error==ETIMEDOUT;
    }
    return 0;
}

void pp_ipc_stop(void) {
    if(connection>=0) {ConnectDetach(connection);connection=-1;}
    if(child_pid>0) {
        kill((pid_t)child_pid,SIGTERM);
        while(waitpid((pid_t)child_pid,NULL,0)<0 && errno==EINTR) {}
        child_pid=0;
    }
}
