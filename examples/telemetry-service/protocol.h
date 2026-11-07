#ifndef PP_TELEMETRY_PROTOCOL_H
#define PP_TELEMETRY_PROTOCOL_H
#include <stdint.h>
#include <sys/iomsg.h>
#define PP_SERVICE_NAME "pulseproof-telemetry"
#define PP_READ_SAMPLE (_IO_MAX+51)
#define PP_SERVICE_PROTOCOL 1
typedef struct { uint16_t type,version;uint32_t sequence; } pp_read_request;
typedef struct { uint32_t sequence,build_id;int32_t value_millicelsius;uint64_t instance; } pp_read_reply;
#endif
