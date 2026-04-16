# Session Wrap-Up — 2026-04-16
## WireGuard Tunnel: Frankfurt ↔ TLV

### Status

| Item | Status |
|------|--------|
| WireGuard installed (both sides) | ✅ Done |
| Handshake Frankfurt ↔ TLV | ✅ Working |
| SSH key to TLV (no password) | ✅ Working |
| Traffic routing through tunnel | ❌ Routing problem |

### Infrastructure Details

| Parameter | Value |
|-----------|-------|
| Frankfurt IP (public) | 31.97.38.112 |
| Frankfurt Tailscale | 100.65.134.34 |
| Frankfurt WG IP | 10.10.10.1 |
| Frankfurt WG Public Key | `TA4QvKyaFPj9CebB/4wH648ZeshH20nsyjqXdgdivUQ=` |
| TLV IP (public) | 188.191.147.234 |
| TLV SSH Key | ~/.ssh/kamatera_tlv |
| TLV WG IP | 10.10.10.2 |
| TLV WG Public Key | `yNUhE+lngzHz+XyRW57WYFZiyEUpA8g5HpRMvigyMQw=` |

### Problem

Frankfurt cannot ping 8.8.8.8 via wg-il interface.
TLV has `ip_forward=1` and MASQUERADE on eth0 — but traffic not forwarding.

### Root Cause (Suspected)

`DEFAULT_FORWARD_POLICY=DROP` in UFW (`/etc/default/ufw`) blocks forwarding
even when iptables MASQUERADE rules are correct.

### Fix (Next Session)

```bash
# 1. Check UFW forward policy on TLV
ssh -i ~/.ssh/kamatera_tlv root@188.191.147.234 \
  "cat /etc/default/ufw | grep DEFAULT_FORWARD"

# 2. If DROP — fix it
ssh -i ~/.ssh/kamatera_tlv root@188.191.147.234 \
  "sed -i 's/DEFAULT_FORWARD_POLICY=\"DROP\"/DEFAULT_FORWARD_POLICY=\"ACCEPT\"/' /etc/default/ufw && ufw reload"

# 3. Verify FORWARD rules
ssh -i ~/.ssh/kamatera_tlv root@188.191.147.234 \
  "iptables -L FORWARD -v -n"

# 4. Test from Frankfurt
ssh root@100.65.134.34 "ping -c 4 -I wg-il 8.8.8.8"
```

### Resume Command

To continue next session, send:
> "המשך WireGuard routing — UFW fix על TLV"
