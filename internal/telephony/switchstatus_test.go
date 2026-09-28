// SPDX-License-Identifier: Apache-2.0

package telephony

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// The fixtures in testdata/switchstatus are the api/response bodies of a live
// v0.1.1 stack (the release's switch image, FreeSWITCH 1.11.3), cut out of the
// raw event-socket stream by Content-Length — byte for byte what Adapter
// receives. File names are the command with spaces as underscores.

func switchReply(t *testing.T, cmd string) string {
	t.Helper()
	name := strings.ReplaceAll(cmd, " ", "_") + ".txt"
	b, err := os.ReadFile(filepath.Join("testdata", "switchstatus", name))
	if err != nil {
		t.Fatalf("no captured reply for %q: %v", cmd, err)
	}
	return string(b)
}

func capturedSwitch(t *testing.T) (*Adapter, *fakeCommander) {
	a, c := newTestAdapter()
	c.replyFor = func(cmd string) (string, error) { return switchReply(t, cmd), nil }
	return a, c
}

func TestProfilesAreReadWithTheAddressTheyAdvertise(t *testing.T) {
	t.Parallel()
	a, _ := capturedSwitch(t)

	got, err := a.Profiles()
	if err != nil {
		t.Fatalf("profiles: %v", err)
	}
	want := map[string]SwitchProfile{
		"internal":      {Name: "internal", IsRunning: true, AdvertisedMediaIP: "192.168.31.111"},
		"external":      {Name: "external", IsRunning: true, AdvertisedMediaIP: "192.168.31.111"},
		"internal-ipv6": {Name: "internal-ipv6", IsRunning: true},
		"external-ipv6": {Name: "external-ipv6", IsRunning: true},
	}
	if len(got) != len(want) {
		t.Fatalf("read %d profiles, want %d — the alias and the gateway in the "+
			"same table are not profiles: %+v", len(got), len(want), got)
	}
	for _, p := range got {
		if p != want[p.Name] {
			t.Errorf("profile %q = %+v, want %+v", p.Name, p, want[p.Name])
		}
	}
}

func TestAProfileThatIsNotRunningSaysSo(t *testing.T) {
	t.Parallel()
	out := strings.Replace(switchReply(t, "sofia status"),
		"sip:mod_sofia@192.168.31.111:5080\tRUNNING (0)",
		"sip:mod_sofia@192.168.31.111:5080\tDOWN", 1)
	if !strings.Contains(out, "\tDOWN") {
		t.Fatal("the fixture no longer has the row this test edits")
	}
	for _, p := range parseProfiles(out) {
		if p.IsRunning != (p.Name != "external") {
			t.Errorf("profile %q running=%v", p.Name, p.IsRunning)
		}
	}
}

func TestTheBotGatewayIsUpWhenTheSwitchSaysItAnswers(t *testing.T) {
	t.Parallel()
	a, c := capturedSwitch(t)

	up, err := a.GatewayUp("aicc_bot")
	if err != nil || !up {
		t.Fatalf("GatewayUp = %v, %v; want up — the capture says Status UP "+
			"(and State NOREG, which is not the question)", up, err)
	}
	if c.last() != "sofia status gateway aicc_bot" {
		t.Errorf("sent %q", c.last())
	}
}

func TestAGatewayThatStoppedAnsweringIsDown(t *testing.T) {
	t.Parallel()
	a, c := newTestAdapter()
	c.reply = strings.Replace(switchReply(t, "sofia status gateway aicc_bot"),
		"Status  \tUP", "Status  \tDOWN", 1)
	if !strings.Contains(c.reply, "Status  \tDOWN") {
		t.Fatal("the fixture no longer has the line this test edits")
	}

	if up, err := a.GatewayUp("aicc_bot"); err != nil || up {
		t.Fatalf("GatewayUp = %v, %v; want down", up, err)
	}
}

func TestAGatewayTheSwitchDoesNotHaveIsAConfigurationFault(t *testing.T) {
	t.Parallel()
	a, _ := capturedSwitch(t)

	up, err := a.GatewayUp("no_such_gw")
	if up || !errors.Is(err, ErrUnknownGateway) {
		t.Fatalf("GatewayUp = %v, %v; want ErrUnknownGateway", up, err)
	}
}

// "RTP-IP" is a line of its own right above "Ext-RTP-IP"; a suffix or prefix
// match would read the container's private address as the advertised one.
func TestAFieldIsMatchedByItsWholeName(t *testing.T) {
	t.Parallel()
	detail := switchReply(t, "sofia status profile internal")
	if got := statusField(detail, "RTP-IP"); got != "10.130.0.3" {
		t.Errorf("RTP-IP = %q", got)
	}
	if got := statusField(detail, "Ext-RTP-IP"); got != "192.168.31.111" {
		t.Errorf("Ext-RTP-IP = %q", got)
	}
}
