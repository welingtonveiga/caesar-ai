# 08 — Sandboxed code execution (Tier 2)

**What to build:** Caesar can run generated code safely: asked to transform a data file, a task writes a script and executes it inside an Apple Container with networking fully disabled, the task's input directory mounted read-only at `in/` and its output directory read-write at `out/`. Results flow back into the task and on to the chat. Execution goes through a `SandboxRunner` protocol (`run(code, in_dir, out_dir, limits) → result`) so a Docker backend can be added later without touching the engine. A missing package fails gracefully with the package named in the report, per the prebaked-image policy.

**Blocked by:** 07 — Task promotion + background execution.

**Status:** ready-for-agent

- [ ] `SandboxRunner` protocol defined; the engine and tools depend only on the protocol
- [ ] Apple Container backend: no network, `in/` mounted ro, `out/` mounted rw, execution limits applied
- [ ] Prebaked image with the pinned common-package set (pandas, numpy, openpyxl, pillow, matplotlib, beautifulsoup4, …) and a documented rebuild command
- [ ] Code-execution tool is classified Tier 2: autonomous, always via the sandbox, only within a task
- [ ] Missing-package runs fail gracefully and the report names the missing package
- [ ] Engine tests use a fake runner (no container needed); a separately-marked integration test exercises the real Apple Container backend
