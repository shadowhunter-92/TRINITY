# Laboratory threat model and safety boundary

**Not certified for industrial, medical, financial or safety-critical production use.** Local experiments can fail and should use non-sensitive synthetic data.

## Design defaults

1. **Offline first:** Compute and Data perform no networking. Industrial simulated modes perform no networking.
2. **Fail closed:** The Modbus client raises `PermissionError` unless `enable_network=True` (or `--enable-network`).
3. **Remote gate:** Any non-loopback target additionally requires both `allow_remote=True` and `authorized=True` (CLI `--allow-remote --i-have-authorization`). This is a deliberate acknowledgement, not cryptographic proof of authorization.
4. **Read only:** The Modbus code supports only FC03/FC04; no coil/register writes, configuration changes, or firmware updates.
5. **Protocol bounds:** 1–125 registers, valid 16-bit addresses, valid unit IDs, bounded response framing, transaction and function matching, 0.05–10s timeouts.
6. **No secrets:** Source code contains no credentials, keys, tokens or customer endpoints; the fixture is synthetic.
7. **No automatic discovery:** No PLC scanning, broadcast, continuous monitoring or connection to an unapproved host.
8. **Validation:** Fixture formats and decoded values are bounded and validated; fuzzing remains future work.

## Why read-only does not equal safe

Classic Modbus TCP usually lacks authentication and confidentiality, and even read requests can increase traffic or workload on fragile legacy equipment. Device behavior and safety depend on the facility and its change-control processes. **Do not connect these scripts directly to production OT networks** without written site authorization, an OT engineer and an approved gateway/test plan.

For real deployments, prefer vetted OPC UA or secure industrial gateways, segmentation, authenticated access, allowlists, monitored egress, least privilege, explicit maintenance windows, approved polling rates and resilience tests.

## Explicit lab example

Local simulated Modbus service at `127.0.0.1:15020`:

```bash
python -m trinitylab.industrial modbus-read --host 127.0.0.1 --port 15020 --address 100 --count 3 --enable-network
```

If no simulator is running, the connection should fail. The automated test suite starts and tears down a loopback simulator as needed.

Remote connections require site authorization. Those extra flags do not establish a secure tunnel or authenticate the target. No production-ready remote CLI example is intentionally provided.

## Risk register

| Threat / failure | Current mitigation | Remaining limitation |
| --- | --- | --- |
| Unintentional device contact | Network off; loopback first; two remote acknowledgements | CLI acknowledgements can be misused; not an authorization system |
| PLC write / unsafe actuation | No write function codes implemented | Read traffic itself can disrupt fragile systems |
| Malformed network response | Framing, length, transaction and function validation, timeouts | No fuzzing, TLS, certificates, or comprehensive interoperability testing |
| Sensitive data collection | Synthetic fixtures; no uploads or telemetry | User-selected `--output` can persist data to disk |
| Supply-chain dependencies | No mandatory third-party runtime dependencies | Python/runtime/OS still have their own vulnerabilities |
| Resource exhaustion | Bound inputs and register quantities | Very large allowed synthetic workloads can still use significant RAM/CPU |
| False semantic mapping | Units and plausibility checks, version drift | Cannot establish ground-truth physical semantics |
| Misleading performance claim | Benchmark scope and limitations in every report | No actual production workloads yet |

## Responsible future engineering

Before a paid industrial pilot: OT threat modeling, formal protocol testing, static analysis, fuzzing, property-based tests, authentication and encrypted transport through a vetted gateway, network architecture review, hardware-in-the-loop simulator, site signoff, incident recovery, deployment rollback and alignment to applicable ISA/IEC 62443 requirements.

## Vulnerability reports

For this laboratory snapshot, review issues privately with the maintainers before sharing exploit details publicly. This repository is not backed by a staffed incident response team or a production patch SLA.
