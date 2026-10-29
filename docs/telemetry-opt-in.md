# Optional SDK activity reporting (opt-in only)

EnergyChain is an open-source, offline-first Python SDK. **Installing, importing,
or using the SDK does not send telemetry.** It works without an EnergyChain
account or a network connection.

For developers who want to help us understand adoption, we offer a voluntary
example:

```bash
python -m pip install energychain
python examples/opt_in_usage_telemetry.py --opt-in
```

**What is sent (only when you run the command with `--opt-in`):**
- a randomly generated installation UUID, stored locally in
  `~/.config/energychain/opt-in-instance-id` on typical Unix systems
  (or in `XDG_CONFIG_HOME`);
- the installed EnergyChain package version;
- the event name and explicit opt-in flag.

No energy readings, device IDs, credentials, prompts, file paths from your
application, code, email address, or customer data are included. The server
hashes the installation ID before private storage; it uses the signal for
aggregate opt-in instance activity. It does not verify identity or represent
unique people, and signals can be self-reported. Standard network connections
may expose an IP address to hosting infrastructure, but EnergyChain does not
intentionally store IP addresses in these telemetry events.

The site also displays separate public *PyPI download counts*. Downloads are
**not** unique installs, active users, or verified SDK accounts.

To stop reporting, simply don't run the example again. It creates no daemon,
scheduled task, import hook, or persistent opt-in setting. Removing the local
identifier resets it; it does not delete previously submitted aggregate events.

Reporting endpoint:
`https://energychain.app/api/sdk-telemetry`

You may use the SDK entirely without this feature. Production workloads
and hosted developer APIs are not currently instrumented by this optional
example. Contact `kolade@energychain.app` with privacy questions.
