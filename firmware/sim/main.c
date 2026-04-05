/**
 * @file    main.c
 * @brief   Entry point for simulation firmware runtime loop.
 */

#include <ps_app.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <time.h>
#endif

#include "board_sim_config.h"

static bool parse_port_u16(const char* text, uint16_t* out) {
	char* end = NULL;
	unsigned long value = 0;

	if ((text == NULL) || (out == NULL)) {
		return false;
	}

	value = strtoul(text, &end, 10);
	if ((end == text) || (end == NULL) || (*end != '\0')) {
		return false;
	}
	if ((value == 0UL) || (value > 65535UL)) {
		return false;
	}

	*out = (uint16_t)value;
	return true;
}

static uint16_t resolve_sim_port(int argc, char** argv) {
	uint16_t port = 9000u;
	const char* env_port = getenv("PS_SIM_PORT");

	if ((env_port != NULL) && (env_port[0] != '\0')) {
		uint16_t parsed_env = 0u;
		if (!parse_port_u16(env_port, &parsed_env)) {
			fprintf(stderr, "Invalid PS_SIM_PORT='%s' (expected 1..65535)\n", env_port);
			exit(2);
		}
		port = parsed_env;
	}

	for (int i = 1; i < argc; ++i) {
		if ((strcmp(argv[i], "--port") == 0) || (strcmp(argv[i], "-p") == 0)) {
			uint16_t parsed_cli = 0u;
			if ((i + 1 >= argc) || (!parse_port_u16(argv[i + 1], &parsed_cli))) {
				fprintf(stderr, "Invalid --port value (expected 1..65535)\n");
				exit(2);
			}
			port = parsed_cli;
			++i;
			continue;
		}

		if (strcmp(argv[i], "--help") == 0) {
			printf("Usage: powerscope-fw-sim [--port <1..65535>]\n");
			printf("  --port, -p   TCP listen port (default: 9000, env: PS_SIM_PORT)\n");
			exit(0);
		}
	}

	return port;
}

static void sleep_1ms(void) {
#if defined(_WIN32)
	Sleep(1);
#else
	const struct timespec ts = {.tv_sec = 0, .tv_nsec = 1000000L};
	nanosleep(&ts, NULL);
#endif
}

int main(int argc, char** argv) {
	const uint16_t sim_port = resolve_sim_port(argc, argv);
	board_sim_set_tcp_port(sim_port);

	ps_app_init();

	while (1) {
		ps_app_tick();
		sleep_1ms();
	}
}
