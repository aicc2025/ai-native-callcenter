// SPDX-License-Identifier: Apache-2.0

package voice

import (
	"bytes"
	"log/slog"
	"net"
	"net/netip"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/rasonyang/ai-native-callcenter/internal/media"
)

// lockedBuffer is a log sink the UAS's receive goroutine and the test can
// share.
type lockedBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *lockedBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *lockedBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

func TestPeerACL(t *testing.T) {
	t.Parallel()
	acl := peerACL{
		netip.MustParsePrefix("10.130.0.0/24"),
		netip.MustParsePrefix("192.168.31.55/32"),
	}
	tests := []struct {
		addr string
		want bool
	}{
		{"10.130.0.20", true},
		{"10.130.1.20", false},
		{"192.168.31.55", true},
		{"192.168.31.56", false},
		{"127.0.0.1", false},
		// A dual-stack socket reports an IPv4 peer in its mapped form.
		{"::ffff:10.130.0.20", true},
	}
	for _, tt := range tests {
		if got := acl.allows(netip.MustParseAddr(tt.addr)); got != tt.want {
			t.Errorf("allows(%s) = %v, want %v", tt.addr, got, tt.want)
		}
	}
	if !(peerACL(nil)).allows(netip.MustParseAddr("203.0.113.7")) {
		t.Error("an empty list refused a peer; empty must allow every peer")
	}
}

// The RTP receive loop asks once per packet.
func TestPeerACLDoesNotAllocate(t *testing.T) {
	acl := peerACL{netip.MustParsePrefix("10.130.0.0/24"), netip.MustParsePrefix("127.0.0.1/32")}
	addr := netip.MustParseAddr("127.0.0.1")
	if allocs := testing.AllocsPerRun(1000, func() { acl.allows(addr) }); allocs != 0 {
		t.Errorf("allows allocates %.0f times per call, want 0", allocs)
	}
}

func TestRequestName(t *testing.T) {
	t.Parallel()
	tests := map[string]string{
		"INVITE sip:aicc@x SIP/2.0\r\n":  "INVITE",
		"OPTIONS sip:x SIP/2.0":          "OPTIONS",
		"\x00\x01garbage":                "",
		"AVERYLONGTOKENWITHNOSPACEATALL": "AVERYLONGTOKENWI",
	}
	for in, want := range tests {
		if got := requestName([]byte(in)); got != want {
			t.Errorf("requestName(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestListedPeerIsServedAsBefore(t *testing.T) {
	_, hooks, p := startUAS(t, func(c *Config) {
		c.AllowedPeers = []netip.Prefix{netip.MustParsePrefix("127.0.0.1/32")}
	})

	// The switch's gateway ping must keep being answered, or the gateway is
	// marked down and no bot call is placed at all.
	p.request("OPTIONS", "")
	if reply := p.await(time.Second); reply.statusCode != 200 {
		t.Fatalf("OPTIONS got %d, want 200", reply.statusCode)
	}

	p.cseq++
	p.request("INVITE", p.offer())
	if trying := p.await(time.Second); trying.statusCode != 100 {
		t.Fatalf("first response was %d, want 100 Trying", trying.statusCode)
	}
	p.awaitStatus(200, 2*time.Second)
	p.request("ACK", "")
	select {
	case <-hooks.started:
	case <-time.After(2 * time.Second):
		t.Fatal("a call from a listed peer never started")
	}
}

// The peer here is a real socket on 127.0.0.1, sending to a real listener that
// lists only 10.0.0.0/8.
func TestUnlistedPeerIsIgnored(t *testing.T) {
	logs := &lockedBuffer{}
	uas, hooks, p := startUAS(t, func(c *Config) {
		c.AllowedPeers = []netip.Prefix{netip.MustParsePrefix("10.0.0.0/8")}
		c.Logger = slog.New(slog.NewTextHandler(logs, nil))
	})

	p.request("OPTIONS", "")
	p.cseq++
	p.request("INVITE", p.offer())
	p.request("INVITE", p.offer()) // a retransmission, or a scanner's second try

	if msg, err := p.read(500 * time.Millisecond); err == nil {
		t.Fatalf("an unlisted peer got a response: %d %s", msg.statusCode, msg.method)
	}
	if n := uas.ActiveCalls(); n != 0 {
		t.Errorf("%d dialogs exist for an unlisted peer, want none", n)
	}
	uas.mu.Lock()
	usedPorts := len(uas.usedPorts)
	uas.mu.Unlock()
	if usedPorts != 0 {
		t.Errorf("%d RTP ports were allocated for an unlisted peer, want none", usedPorts)
	}
	select {
	case <-hooks.started:
		t.Error("a call from an unlisted peer started")
	case err := <-hooks.failed:
		t.Errorf("a call from an unlisted peer got as far as failing: %v", err)
	default:
	}

	out := logs.String()
	if got := strings.Count(out, "peer is not in AICC_BOT_ALLOWED_PEERS"); got != 1 {
		t.Errorf("logged %d refusals for three requests inside one interval, want 1:\n%s", got, out)
	}
	from := p.sip.LocalAddr().(*net.UDPAddr).String()
	if !strings.Contains(out, "from="+from) || !strings.Contains(out, "request=OPTIONS") {
		t.Errorf("the refusal does not name the peer %s and its request:\n%s", from, out)
	}
}

// Audio sent to a call's port from outside the list must not reach the
// conversation as though the caller had said it.
func TestRTPFromAnUnlistedSourceIsDiscarded(t *testing.T) {
	t.Parallel()

	receive := func(allowed peerACL) bool {
		session := NewRTPSession(0, media.LawMu, -1, nil)
		session.allowed = allowed
		sender, err := net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1)})
		if err != nil {
			t.Fatalf("sender socket: %v", err)
		}
		defer sender.Close()
		if err := session.Start(sender.LocalAddr().(*net.UDPAddr)); err != nil {
			t.Fatalf("start rtp: %v", err)
		}
		defer session.Stop()

		target := &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1), Port: session.LocalPort}
		// A burst, so one lost datagram cannot decide the outcome.
		for seq := range uint16(8) {
			packet := packRTPHeader(make([]byte, 0, 200), 100+seq, uint32(seq)*160, 0xABCD, 0)
			packet = append(packet, make([]byte, media.FrameSamples)...)
			if _, err := sender.WriteToUDP(packet, target); err != nil {
				t.Fatalf("send rtp: %v", err)
			}
		}
		deadline := time.Now().Add(500 * time.Millisecond)
		for time.Now().Before(deadline) {
			if session.received.Load() > 0 {
				return true
			}
			time.Sleep(10 * time.Millisecond)
		}
		return false
	}

	if !receive(peerACL{netip.MustParsePrefix("127.0.0.0/8")}) {
		t.Fatal("RTP from a listed source was not received")
	}
	if receive(peerACL{netip.MustParsePrefix("10.0.0.0/8")}) {
		t.Error("RTP from an unlisted source was accepted as the caller's audio")
	}
}
