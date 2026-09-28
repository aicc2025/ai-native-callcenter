// SPDX-License-Identifier: Apache-2.0

package voice

import (
	"log/slog"
	"net/netip"
	"sync"
	"time"
)

// peerACL is the set of addresses allowed to talk to the bot: its SIP
// listener and the RTP and RTCP ports of every call. Empty allows everyone,
// which is what a deployment that has not configured one has always done.
type peerACL []netip.Prefix

// allows reports whether addr may send to the bot. It does not allocate: the
// RTP receive loop asks once per packet.
func (a peerACL) allows(addr netip.Addr) bool {
	if len(a) == 0 {
		return true
	}
	addr = addr.Unmap()
	for _, prefix := range a {
		if prefix.Contains(addr) {
			return true
		}
	}
	return false
}

// deniedPeerLogInterval bounds how often a refused peer is reported. A scanner
// sends thousands of requests, and one WARN each would bury everything else in
// the log.
const deniedPeerLogInterval = 10 * time.Second

// deniedPeerLog reports refused SIP requests: the first at once, the rest at
// most once per interval, with a count of what was not reported in between.
type deniedPeerLog struct {
	log *slog.Logger

	mu         sync.Mutex
	lastAt     time.Time
	suppressed int
}

func (d *deniedPeerLog) report(peer netip.AddrPort, request string) {
	now := time.Now()
	d.mu.Lock()
	if !d.lastAt.IsZero() && now.Sub(d.lastAt) < deniedPeerLogInterval {
		d.suppressed++
		d.mu.Unlock()
		return
	}
	suppressed := d.suppressed
	d.lastAt, d.suppressed = now, 0
	d.mu.Unlock()

	d.log.Warn("sip request dropped: peer is not in AICC_BOT_ALLOWED_PEERS",
		"from", peer.String(), "request", request, "droppedUnreported", suppressed)
}

// requestName is the first token of a datagram — the method of a request, or
// "SIP/2.0" for a response — for the log line about a refused peer. It is
// bounded and read without parsing, because nothing from that peer is parsed.
func requestName(data []byte) string {
	const maxLen = 16
	for i, b := range data {
		if i == maxLen || b <= ' ' || b > '~' {
			return string(data[:i])
		}
	}
	return string(data)
}
