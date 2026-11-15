# Device recovery after configuring with an older version

## Background

Versions of `configure-using-downlinks.py` before the 2026 audit fixes wrote every bit field
mirrored (most significant bit first, while the Oyster 3 numbers bits from the least
significant bit) and wrote multi-byte fields big-endian instead of little-endian. Every
downlink built with such a version reached the device with other values than intended:
for example downlink 1 disabled the fixes at the start and end of trips and switched off
the statistics uplinks, downlink 9 set 4 frame repetitions (NbTrans) instead of 1 and swapped
the ADR timing values, and downlink 31 switched off the GPS constellation.

This runbook helps you find out which downlinks the device accepted and restore the
defaults. **You decide and you send; nothing in this repository sends anything by itself.**

## 1. Which downlinks did the device accept?

```bash
$ python ./ack.py --history --hours 720
```

This lists every acknowledgement (Uplink 2) still in the Storage Integration (TTN keeps
30 days), with time, sequence number, accepted and downlink port. For older history, import
your old snapshots first (`python ./import-snapshots.py`) and look at the port 2 uplinks in
the local database.

The old script sent a sequence number `n` from `config.yaml` as `2·n`, so an
acknowledgement with an **even** sequence number may come from the old script. **Odd**
sequence numbers were sent another way (for example the TTN Console) and are not affected
by this bug.

Every port with an accepted acknowledgement from the old script should be restored. Pay
special attention to ports 1, 9, 30, 31, 32 and 35.

## 2. Check the payloads before sending

Run a dry-run for each downlink and compare the payload with the expected value (shown for
sequence number 1; only the first byte changes with another sequence number):

```bash
$ python ./configure-using-downlinks.py --downlink 1
downlink1 Byte Array: 01981e8a8a1f0201
$ python ./configure-using-downlinks.py --downlink 9
downlink9 Byte Array: 010711ff567f00
```

Use a new sequence number for every attempt, for example `--sequencenumber 11`, so that
each acknowledgement can be matched to exactly one attempt.

## 3. Send and wait for the acknowledgement

```bash
$ python ./configure-using-downlinks.py --downlink 1 --sequencenumber 11 --send
$ python ./configure-using-downlinks.py --downlink 9 --sequencenumber 12 --send
```

The device acknowledges once, with its next uplink, and the Storage Integration is not
real-time. If the script stops waiting, check later with
`python ./ack.py --downlink 1 --sequencenumber 11`.

## 4. Check that the statistics come back

Downlink 1 from the old script disabled the statistics uplinks. After restoring it, ask for
the statistics with downlink 35 (poll): set "0.7 Send Downlink Ack", "1.0 Send Device
Statistics (Uplink 3)" and "1.1 Send Device Statistics V3 (Uplink 31)" to `true` and
"1.2 Apply Poll Position Count and Poll Position Period" to `false` in `config.yaml`. With
sequence number 1 the payload is `810300000000`.

```bash
$ python ./configure-using-downlinks.py --downlink 35 --sequencenumber 13 --send
$ python ./uplinks.py --hours 48 --port 3 --port 31
```

Afterwards, set downlink 35 in `config.yaml` back to its defaults.

## 5. Check the network side

In the TTN Console, open the end device and check:

* the MAC settings / MAC state: the number of frame repetitions (NbTrans) should be 1;
* the `consumed_airtime` of recent uplinks: with 4 repetitions the device spends four times
  the airtime and battery per uplink.

## 6. Be careful with downlinks 7, 8 and 9

A wrong configuration of downlink 7 (channels and data rates), 8 (JoinEUI) or 9 (advanced
LoRaWAN options) can make the device unreachable. Check every value in the dry-run table
before sending one of these, and send them one at a time.
