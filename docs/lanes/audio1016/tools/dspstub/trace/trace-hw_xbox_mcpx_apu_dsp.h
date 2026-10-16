/* Stand-in for the generated trace header: every DSP trace point is off. */
#ifndef DSPSTUB_TRACE_H
#define DSPSTUB_TRACE_H
#define trace_event_get_state(id) 0
#define trace_dsp_read_peripheral(...) do { } while (0)
#define trace_dsp_write_peripheral(...) do { } while (0)
#define trace_dsp56k_execute_instruction(...) do { } while (0)
#define trace_dsp56k_execute_instruction_disasm(...) do { } while (0)
#endif
