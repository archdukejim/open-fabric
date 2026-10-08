# fabriclib/ntp

Time for the host and its network (design [1.13.1](../../../docs/volume_1_description_and_architecture/1.13.1-chrony.md#11311-status)): chrony on the host.

| File | What |
|---|---|
| `normalize_ntp.py` | Check the time settings (`ntp_servers` "<host> [nts] [pool] [prefer]", `ntp_serve`, `ntp_set_clock`) before anything is rendered |
| `chrony_settings.py` | What chrony.conf needs: the sources (this site's upstream site first) and the networks it answers |
| `deploy_chrony.py` | Deploy step: chrony.conf, chrony's start options (-s: no RTC; -x: never set the clock), chrony-wait's limit; timesyncd off, chrony restarted on a change |
| `time_status.py` | This host's synchronisation as chrony reports it (source, stratum, offset; its own clock is not "synchronised") |
| `query_time.py` | How far this clock is from another NTP server, changing nothing (`chronyd -Q`): a site against its upstream site |
