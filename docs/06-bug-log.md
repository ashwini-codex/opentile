# Bug log

One section per bug. Format:

```
## BUG-<id>
- Symptom (first failing cycle / command):
- Root cause (file and line):
- Fix commit:
- Regression test:
```

No RTL bugs logged. Test gaps found during mutation (M17 latency, M32 A `tready`) were closed with tests, not RTL changes.
