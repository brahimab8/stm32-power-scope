/**
 * @file    comm_tcp.c
 * @brief   Non-blocking TCP transport backend for simulation firmware.
 */

#include "comm_tcp.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(_WIN32)
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET ps_sock_t;
#define PS_INVALID_SOCK INVALID_SOCKET
#define ps_close_socket closesocket
#else
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int ps_sock_t;
#define PS_INVALID_SOCK (-1)
#define ps_close_socket close
#endif

#define TCP_RX_CHUNK (1024u)
#define TCP_TX_MAX_CHUNK (1024u)

static ps_sock_t s_listen_sock = PS_INVALID_SOCK;
static ps_sock_t s_client_sock = PS_INVALID_SOCK;
static ps_transport_rx_cb_t s_rx_cb = NULL;
static bool s_started = false;

static void set_nonblocking(ps_sock_t sock) {
#if defined(_WIN32)
	u_long mode = 1;
	(void)ioctlsocket(sock, FIONBIO, &mode);
#else
	const int flags = fcntl(sock, F_GETFL, 0);
	if (flags >= 0) {
		(void)fcntl(sock, F_SETFL, flags | O_NONBLOCK);
	}
#endif
}

static bool socket_would_block(void) {
#if defined(_WIN32)
	const int err = WSAGetLastError();
	return (err == WSAEWOULDBLOCK) || (err == WSAEINPROGRESS);
#else
	return (errno == EWOULDBLOCK) || (errno == EAGAIN);
#endif
}

static void drop_client(void) {
	if (s_client_sock != PS_INVALID_SOCK) {
		(void)ps_close_socket(s_client_sock);
		s_client_sock = PS_INVALID_SOCK;
	}
}

bool comm_tcp_init(uint16_t port) {
	struct sockaddr_in addr = {0};
	int opt = 1;

	if (s_started) {
		/* Idempotent init: board layer can call init defensively. */
		return true;
	}

#if defined(_WIN32)
	WSADATA wsa_data;
	if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0) {
		return false;
	}
#endif

	s_listen_sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	if (s_listen_sock == PS_INVALID_SOCK) {
		return false;
	}

	(void)setsockopt(s_listen_sock, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));

	addr.sin_family = AF_INET;
	addr.sin_addr.s_addr = htonl(INADDR_ANY);
	addr.sin_port = htons(port);

	if (bind(s_listen_sock, (struct sockaddr*)&addr, (socklen_t)sizeof(addr)) != 0) {
		ps_close_socket(s_listen_sock);
		s_listen_sock = PS_INVALID_SOCK;
		return false;
	}

	if (listen(s_listen_sock, 1) != 0) {
		ps_close_socket(s_listen_sock);
		s_listen_sock = PS_INVALID_SOCK;
		return false;
	}

	/* Run non-blocking and poll-driven */
	set_nonblocking(s_listen_sock);
	s_started = true;
	return true;
}

void comm_tcp_set_rx_handler(ps_transport_rx_cb_t cb) {
	s_rx_cb = cb;
}

uint16_t comm_tcp_best_chunk(void) {
	return TCP_TX_MAX_CHUNK;
}

bool comm_tcp_link_ready(void) {
	return (s_client_sock != PS_INVALID_SOCK);
}

int comm_tcp_try_write(const uint8_t* buf, uint16_t len) {
	int sent = 0;

	if ((buf == NULL) || (len == 0u) || (len > TCP_TX_MAX_CHUNK)) {
		/* Contract violation by caller. */
		return -1;
	}

	if (s_client_sock == PS_INVALID_SOCK) {
		/* No link yet: not an error, caller can retry later. */
		return 0;
	}

	sent = (int)send(s_client_sock, (const char*)buf, (int)len, 0);
	if (sent < 0) {
		if (socket_would_block()) {
			/* Backpressure on non-blocking socket: retry on next tick. */
			return 0;
		}
		/* Hard socket error: drop peer and force reconnect. */
		drop_client();
		return -1;
	}

	if ((uint16_t)sent != len) {
		/*
		 * Treat partial writes as "not committed" at this layer.
		 * Frames should be retried by the TX path as a whole.
		 */
		return 0;
	}

	return sent;
}

void comm_tcp_poll(void) {
	uint8_t rx_buf[TCP_RX_CHUNK];

	if (s_listen_sock == PS_INVALID_SOCK) {
		return;
	}

	if (s_client_sock == PS_INVALID_SOCK) {
		/* One active host client at a time. */
		ps_sock_t candidate = accept(s_listen_sock, NULL, NULL);
		if (candidate != PS_INVALID_SOCK) {
			set_nonblocking(candidate);
			s_client_sock = candidate;
		}
	}

	if (s_client_sock != PS_INVALID_SOCK) {
		/* Drain all currently available RX bytes in this tick. */
		while (1) {
			const int n = (int)recv(s_client_sock, (char*)rx_buf, (int)sizeof(rx_buf), 0);
			if (n > 0) {
				if (s_rx_cb != NULL) {
					/* Forward raw bytes to core parser/dispatcher. */
					s_rx_cb(rx_buf, (uint32_t)n);
				}
				continue;
			}

			if (n == 0) {
				/* Peer has performed orderly shutdown: drop client and wait for reconnect. */
				drop_client();
				break;
			}

			if (socket_would_block()) {
				/* No more RX data this tick. */
				break;
			}

			/* Any other recv error => reset link and wait for reconnect. */
			drop_client();
			break;
		}
	}
}

