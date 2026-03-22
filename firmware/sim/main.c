/**
 * @file    main.c
 * @brief   Entry point for simulation firmware runtime loop.
 */

#include <ps_app.h>

#include <stdint.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <time.h>
#endif

#include "comm_tcp.h"

static void sleep_1ms(void) {
#if defined(_WIN32)
	Sleep(1);
#else
	const struct timespec ts = {.tv_sec = 0, .tv_nsec = 1000000L};
	nanosleep(&ts, NULL);
#endif
}

int main(void) {
	ps_app_init();

	while (1) {
		comm_tcp_poll();
		ps_app_tick();
		sleep_1ms();
	}
}
