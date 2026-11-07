#include "pp.h"
#include <pthread.h>
#include <stdatomic.h>

static atomic_int running;
static pthread_t threads[8];
static unsigned active;

static void *worker(void *unused) {
    (void)unused;
    while(atomic_load(&running)) { pp_busy_us(8000); pp_sleep_us(2000); }
    return NULL;
}

int pp_load_start(unsigned count) {
    pthread_attr_t attributes;
    int rc=pthread_attr_init(&attributes);
    if(rc) return rc;
    rc=pthread_attr_setinheritsched(&attributes,PTHREAD_INHERIT_SCHED);
    if(rc) {pthread_attr_destroy(&attributes);return rc;}
    atomic_store(&running,1);
    for(active=0;active<count;++active) {
        rc=pthread_create(&threads[active],&attributes,worker,NULL);
        if(rc) { pthread_attr_destroy(&attributes);pp_load_stop(); return rc; }
    }
    pthread_attr_destroy(&attributes);
    return 0;
}

void pp_load_stop(void) {
    atomic_store(&running,0);
    for(unsigned i=0;i<active;++i) pthread_join(threads[i],NULL);
    active=0;
}
